#!/usr/bin/python
#-*-coding:utf-8 -*-
import sys
import locale
import os
import collections
import time
import subprocess
import platform
import socket
import thread
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4.QtSql import *


global run_system
global language

def getFormatTime(fmt):
	curtime = time.strftime("%s" %fmt,time.localtime())
	return curtime

class SignalObject(QObject):
        compilerSignal = pyqtSignal(str,int)
        networkSignal = pyqtSignal(str)

class ClientSend(QRunnable):
	def __init__(self,client,message,col,out):
		QRunnable.__init__(self)
		self.obj = SignalObject()
		self.client = client
		self.message = message
		self.col = col
		self.out = out

	def run(self):
		if self.message.split(":")[0] == "get":
			files = []
			self.client.client.send("%s" %self.message)
			if self.col == 0 or self.col == 2:
				filename = "%s" %self.out+"\\"+"kernel_"+getFormatTime("%m%d%H%M")+".img"
				files.append(filename)
			if self.col == 1 or self.col == 2:
				filename = "%s" %self.out+"\\"+"cn1100_linux_"+getFormatTime("%m%d%H%M")+".ko"
				files.append(filename)
			for i in range(0,len(files)):
				fp = open(files[i],"wb+")
				while True:
					buf = self.client.client.recv(1024)
					self.client.client.send("success")
					if buf == "complete":
						print "receive image success"
						break
					else:
						fp.write(buf)
		elif self.message.split(":")[0] == "put":
			pass
		elif self.message.split(":")[0] == "compile":
			pass
class NetClient:
        def __init__(self,addr,port,tp):
                self.addr = addr 
                self.port = port
		self.tp = tp
        def connect(self):
                self.client = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                self.client.connect((self.addr,self.port))
                status = self.client.recv(512)
                if status == "success":
                        return True
                else:
                        return False
	
	def sendThread(self,fd):
		thread.exit_thread()
	def sendFile(self,message):
		runnable = ClientSend(self.client,message)
		self.tp.start(runnable)
        def sendMessage(self,message):
                self.client.send(message)
                reply = self.client.recv(512)
		return reply

                

class NetServer(QRunnable):
        def __init__(self,port):
                QRunnable.__init__(self)
		self.kernel = ""
		self.module = "/opt/module/CN1100"
		self.out = ""
		self.toolchain = ""
                self.obj = SignalObject()
                self.host = "192.168.1.105"
                self.port = port
                self.app_closed = False

	def removeDir(self,topdir):
		for root,dirs,files in os.walk(topdir,topdown=False):
			for name in files:
				os.remove(os.path.join(root,name))
			for name in dirs:
				os.rmdir(os.path.join(root,name))
        def run(self):
                self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server.bind((self.host,self.port))
                self.server.listen(5)
                self.client,self.caddr = self.server.accept()
                self.client.send("success")
		self.module = "/opt/module/CN1100"
                while not self.app_closed:
                        message = self.client.recv(512)
			types =  message.split(":")
			if types[0] == "kernel":
				self.kernel = types[1]
				if os.path.exists(types[1]):
					platforms = ""
					lists = os.listdir(types[1])
					for i in range(0,len(lists)):
						platforms += lists[i]
						platforms += ":"
					self.client.send("%s" %platforms)
				else:
					self.client.send("failed")
			elif types[0] == "platform":
				self.platform = types[1]
				self.platform_dir = self.kernel+"/"+"%s" %types[1]
				lists = os.listdir(self.platform_dir)
				venders = ""
				if len(lists) == 0:
					self.client.send("empty")
				else:
					for i in range(0,len(lists)):
						venders += lists[i]
						venders += ":"
					self.client.send(venders)
			elif types[0] == "vender":
				if types[1] != "":
					self.vender = self.platform_dir+"/"+"%s" %types[1]
					lists = os.listdir(self.vender)
					versions = ""
					if len(lists) == 0:
						self.client.send("empty")
					else:
						for i in range(0,len(lists)):
							versions += lists[i]
							versions += ":"
						self.client.send("%s" %versions)
				else:
					self.client.send("empty")
			elif types[0] == "version":
				if types[1] != "":
					self.kversion = self.vender+"/"+"%s" %types[1]
					self.client.send("success")
				else:
					self.client.send("empty")

			elif types[0] == "toolchain":
				if types[1] != "":
					tmp = self.vender+"/"+"%s" %types[1]+"/bin/"
					self.toolchain = tmp
					if os.path.exists(tmp):
						print tmp
						for name in os.listdir(tmp)[0].split("-")[0:-1]:
							print name
							self.toolchain+=name
							self.toolchain+="-"
					else:
						print "path not exist"
					self.client.send("%s" %self.toolchain)
				else:
					self.client.send("empty")

			elif types[0] == "out":
				self.client.send("success")
			elif types[0] == "module":
				self.client.send("ready")
				self.recvFiles()
			elif message == "Kernel":
				what = 0
				if self.kernel == "" or self.toolchain == "":
					print "Kernel or Toolchain missed"
					self.client.send("Failed")
				else:
					result = self.compiler(self.platform,self.kversion,self.module,self.toolchain,what)
					if result:
						self.client.send("ok")
					else:
						self.client.send("fail")
					
			elif message == "Module":
				what = 1
				if self.kernel == "" or self.toolchain == "" or self.module == "":
					print "Kernel or Toolchain or Module missed"
					self.client.send("Failed")
				else:
					self.client.send("running")
					result = self.compiler(self.platform,self.kversion,self.module,self.toolchain,what)
					if result:
						self.client.send("ok")
					else:
						self.client.send("fail")
			elif message == "All":
				if self.kernel == "" or self.toolchain == "" or self.module == "":
					print "Kernel or Toolchain or Module missed"
					self.client.send("Failed")
				else:
					self.client.send("running")
					result = self.compiler(self.platform,self.kversion,self.module,self.toolchain,what)
					if result:
						self.client.send("ok")
					else:
						self.client.send("fail")
			elif types[0] == "get":
				images = []
				if types[1] == "kernel" or types[1] == "all":
					if self.platform == "Rockchip":
						images.append(self.kversion+"/kernel.img")
				if types[1] == "module" or types[1] == "all":
					images.append(self.module+"/cn1100_linux.ko")
				for i in range(0,len(images)):
					print "send %s" %images[i]
					fp = open(images[i],"rb")
					while True:
						buf = fp.read(1024)
						if not buf:
							self.client.send("complete")
							self.client.recv(512)
							break
						else:
							self.client.send(buf)
							self.client.recv(512)
			elif message == "quit":
				self.client.close()
				break
	def compiler(self,platform,kernel,module,toolchain,what):
                compile_status = False
                self.obj.compilerSignal.emit("running",what)
                if (what == 0 or what == 2) and (kernel != ""):
                        compile_status = True
                        if platform == "Samsung":
                                status = subprocess.call(["make","ARCH=arm","CROSS_COMPILE=%s" %self.toolchain,"-C","%s" %kernel,"zImage"])
			elif platform == "Rockchip":
				status = subprocess.call(["make","ARCH=arm","CROSS_COMPILE=%s" %self.toolchain,"-C","%s" %self.kversion,"kernel.img"])
                if (what == 1 or what == 2) and (module != ""):
			print "kernel:"+kernel
                        status = subprocess.call(["make","CROSS_COMPILE=%s" %self.toolchain,"KERNEL=%s" %kernel,"MODULE=%s" %module,"-C","%s" %module])
                        compile_status = True
                if compile_status:
			if status == 0:
				return True
			else:
				return False
                        if what == 2:
                                if (k_status or m_status) == 0:
                                        self.obj.compilerSignal.emit("pass",what)
                                else:
                                        if k_status:
                                                what = 0
                                        elif m_status:
                                                what = 1
                                        self.obj.compilerSignal.emit("fail",what)
                        else:
                                if status:
                                        self.obj.compilerSignal.emit("fail",what)
                                else:
                                        self.obj.compilerSignal.emit("pass",what)
                else:
                        self.obj.compilerSignal.emit("nothing",what)

	def recvFiles(self):
		if os.path.exists(self.module):
			self.removeDir(self.module)
		while True:
			recv = self.client.recv(1024)
			if (recv.split(":")[0][0]) == "D":
				self.client.send("success")
				path = self.module+"/"+recv.split(":")[-1].replace('\x00','')
				os.mkdir(os.path.normpath(path))
			elif (recv.split(":")[0][0]) == "F":
				self.client.send("sReady")
				path = self.module+"/"+recv.split(":")[-1].replace('\x00','')
			        fp = open(path,"wb+")
			        while True:
			        	content = self.client.recv(1024)
			        	self.client.send("success")
			        	if content == "over":
			        		break
			        	fp.write(content)

			if recv == "complete":
				self.client.send("success")
				break;

        def quit(self):
                self.app_closed = True
                self.server.close()



class Compiler(QRunnable):

        def __init__(self,platform,kernel,module,toolchain,what):
                QRunnable.__init__(self)
                self.obj = SignalObject()
                self.platform = platform
                self.kernel = kernel
                self.module = module
                self.what = what
                self.toolchain = toolchain

        def run(self):
                compile_status = False
                self.obj.compilerSignal.emit("running",self.what)
                if (self.what == 0 or self.what == 2) and (self.kernel != ""):
                        if self.platform == "Samsung":
                                k_status = subprocess.call(["make","ARCH=arm","CROSS_COMPILE=%s" %self.toolchain,"-C","%s" %self.kernel,"zImage"])
                                compile_status = True
                                status = k_status;
                if (self.what == 1 or self.what == 2) and (self.module != ""):
                        m_status = subprocess.call(["make","KERNEL=%s" %self.kernel,"MODULE=%s" %self.module,"-C","%s" %self.module])
                        compile_status = True
                        status = m_status
                if compile_status:
                        if self.what == 2:
                                if (k_status or m_status) == 0:
                                        self.obj.compilerSignal.emit("pass",self.what)
                                else:
                                        if k_status:
                                                self.what = 0
                                        elif m_status:
                                                self.what = 1
                                        self.obj.compilerSignal.emit("fail",self.what)
                        else:
                                if status:
                                        self.obj.compilerSignal.emit("fail",self.what)
                                else:
                                        self.obj.compilerSignal.emit("pass",self.what)
                else:
                        self.obj.compilerSignal.emit("nothing",self.what)

class TSTools(QWidget):
        def __init__(self,s):
                super(TSTools,self).__init__()
                self.toolsType = s
                self.top = ""
                self.module = ""
                self.out = ""
                self.toolchain = ""
                self.default = collections.OrderedDict([("kernel",""),("module",""),("out",""),\
                                ("toolchain",""),("platform",""),("vender",""),("version","")])
                self.palette = QPalette()
                self.initDB()           
                self.initUI()
                self.initDT()

	def genLinuxDir(self,lists):
		target = ""
		for i in range(2,len(lists)):
			target += lists[i]+"/"

		return target


	def sendDir(self,topdir):
		dirlist = os.listdir(topdir)
		for f in dirlist:
			curdir = topdir+"\\"+f
			if os.path.isdir(curdir):
				senddir = self.genLinuxDir((curdir).split("\\"))
				tmp = "D:"+senddir
				reply = self.netclient.sendMessage(tmp)
				self.sendDir(curdir)
			elif os.path.isfile(curdir):
				sendfile = self.genLinuxDir((curdir).split("\\"))[:-1]
				reply = self.netclient.sendMessage("F:"+sendfile)
				if reply == "sReady":
					fp = open(curdir,"rb")
					while True:
					       buf = fp.read(1024)
					       if not buf:
						       reply = self.netclient.sendMessage("over")
						       break;
					       reply = self.netclient.sendMessage(buf)
#					       self.netclient.sendFile(buf)

        def closeEvent(self,event):
                print "APP will be closed"
                if self.toolsType == 1:
                        self.netserver.quit()
		elif self.toolsType == 0:
			self.netclient.sendMessage("quit")

        def initDB(self):
                self.first = False
                self.db = QSqlDatabase.addDatabase("QSQLITE") 
                self.db.setDatabaseName("TSTools.db")
                ok = self.db.open()
                if ok:
                        i = 0
                        print "connect database ok"
                        query = QSqlQuery()
                        query.exec_("create table if not exists TSTools(name varchar(128),path varchar(512))")
                        query.exec_("select * from TSTools")
                        while query.next():
                                i += 1
                                key = query.value(0).toString()
                                self.default["%s" %key] = "%s" %query.value(1).toString()
                        if i == 0:
                                for key in self.default.keys():
                                        cmd = "insert into TSTools values(\"%s\",\"""\")" %key
                                        query.exec_(cmd)
                        self.db.close()
                else:
                        print "connect database failed"
        def initDT(self):
                keys = self.default.keys()[4:len(self.default)]
                if self.path.itemAtPosition(0,1).widget().text() != "":
                        for i in range(0,self.lists.rowCount()):
                                for j in range(0,self.lists.columnCount()):
                                        item = self.lists.itemAtPosition(i,j).widget()
                                        for k in range(0,item.count()):
                                                if item.itemText(k) == self.default[keys[j]]:
                                                        item.setCurrentIndex(k)

        def initUI(self):
                if language == 0:
                        self.labels=[u"内核路径",u"模块路径",u"输出路径",u"编译工具"]
                        self.toolnames = [[u"编译内核",u"编译模块",u"编译全部"],[u"输出内核",u"输出模块",u"输出全部"],\
                                        [u"保存参数","",u"重置参数"]]
                elif language == 1:
                        self.labels=["Top Dir","Module Dir","Out Dir","Tool Dir"]
                        self.toolnames = [["Compile Kernel","Compile Module","Compile All"],["Output Kernel","Output Module","Output All"],\
                                        ["Save Paths","","Reset Paths"]]

                self.tp = QThreadPool()

		self.tab_widget = QTabWidget()
		self.tab_widget.currentChanged[int].connect(self.onXXXChanged)
		tab1 = QWidget()
		tab2 = QWidget()
		
		self.tab1_layout = QVBoxLayout(tab1)
		self.tab2_layout = QVBoxLayout(tab2)

		self.tab_widget.addTab(tab1,u"内核编译")
		self.tab_widget.addTab(tab2,u"驱动配置")

                self.tools = QGridLayout()
                for i in range(0,len(self.toolnames)):
                        for j in range(0,len(self.toolnames[0])):
                                if self.toolnames[i][j] == "":
                                        tl = QLineEdit(u"编译状态")
                                        self.status = tl
                                else:
                                        tl = QPushButton(self.toolnames[i][j])
                                        tl.clicked.connect(self.onToolsClicked)
                                self.tools.addWidget(tl,i,j)

                self.lists = QGridLayout()
                for i in range(0,1):
                        for j in range(0,4):
                                cb = QComboBox()
                                cb.currentIndexChanged.connect(self.onCurrentIndexChanged)
                                self.lists.addWidget(cb,i,j)

                self.path = QGridLayout()
                for i in range(0,len(self.labels)):
                        for j in range(0,3):
                                if j == 0:
                                        wg = QLabel(self.labels[i])
                                if j == 1:
                                        wg = QLineEdit()
                                        if run_system == "Linux":
                                                wg.textChanged[str].connect(self.textChanged)
                                        elif run_system == "Windows":
#                                                wg.returnPressed.connect(self.onReturnPressed)
						wg.textChanged[str].connect(self.textChanged)
                                if j == 2:
                                        if run_system == "Linux":
                                                wg = QPushButton(u"浏览")
                                        elif run_system == "Windows":
						if i == 1 or i == 2:
							wg = QPushButton(u"浏览")
						else:
							wg = QPushButton(u"设置")
                                        wg.clicked.connect(self.browseButtonClicked)
                                self.path.addWidget(wg,i,j)

                paths = self.default.keys()[:4]
                for i in range(0,len(paths)):
                        self.path.itemAtPosition(i,1).widget().setText(self.default[paths[i]])

                ##Initialize network here
                if self.toolsType == 1:
                        print "initial server"
                        self.netserver = NetServer(1234)
                        self.netserver.obj.networkSignal.connect(self.onNetWork)
                        self.tp.start(self.netserver)
                elif self.toolsType == 0:
                        self.netclient = NetClient("192.168.1.105",1234,self.tp)
                        status = self.netclient.connect()
                        if status:
                                print "connect to server success"

		self.initConfig()

                mainlayout = QVBoxLayout()
                self.tab1_layout.addLayout(self.path)
                self.tab1_layout.addLayout(self.lists)
                self.tab1_layout.addLayout(self.tools)
		mainlayout.addWidget(self.tab_widget)
                
                self.setLayout(mainlayout)
#                if language == 0:
#                        self.setWindowTitle(u"内核编译")
#                elif language == 1:
#                        self.setWindowTitle("Kernel Compile Tool")
                self.show()

	def initConfig(self):
		self.config_path = ""
		hbox = QHBoxLayout()
		name = QLabel(u"当前文件")
		self.config_title = QLineEdit()
		self.config_title.setReadOnly(True)
		hbox.addWidget(name)
		hbox.addWidget(self.config_title)

		self.configs = QGridLayout()
		for i in range(0,1):
			for j in range(0,3):
				if j == 0:
					if i == 0:
						item = QLabel(u"头文件路径")
				if j == 1:
					if i == 0:
						item = QComboBox()
						item.currentIndexChanged.connect(self.onConfigFileSelect)
				if j == 2:
					if i == 0:
						item = QPushButton(u"浏览")
						item.clicked.connect(self.configButtonClicked)

				self.configs.addWidget(item,i,j)

		vbox = QVBoxLayout()
		vbox.addLayout(hbox)
		vbox.addLayout(self.configs)
		self.tab2_layout.addLayout(vbox)
	def onXXXChanged(self,index):
		print "%d" %index
        def onReturnPressed(self):
                lineEdit = self.sender()
                row,col = self.getPosition(lineEdit,self.path)
		keys = self.default.keys()
		self.netclient.sendMessage(keys[row]+":"+self.sender().text())

        def onNetWork(self):
                pass

        def textChanged(self,text):
                lineEdit = self.sender()
                row,col = self.getPosition(lineEdit,self.path)
                if run_system == "Linux":
                        if row == 0:
                                self.top = lineEdit.text()
                        elif row == 1:
                                self.module = lineEdit.text()
                        elif row == 2:
                                self.out = lineEdit.text()
                        elif row == 3:
                                self.toolchain = lineEdit.text() + "/"
                                tools = os.listdir(self.toolchain)[0]
                                for k in tools.split("-")[0:-1]:
                                        self.toolchain += k + "-"
                                print self.toolchain
                        label = self.path.itemAtPosition(row,0).widget()
                        if label.text() == self.labels[0]:
                                platform = self.lists.itemAtPosition(0,0).widget()
                                platform.clear()
                                for p in os.listdir(self.top):
                                        platform.addItem(p)
		elif run_system == "Windows":
			if row == 1:
				print "send modules"
				reply = self.netclient.sendMessage("module")
				if reply == "ready":
					self.sendDir(self.sender().text())
					self.netclient.sendMessage("complete")
			elif row == 2:
				self.out = lineEdit.text()

        def slotTestSignal(self,status,what):
                if status == "running":
                        if what == 0:
                                if language == 0:
                                        ch = u"内核正在编译中"
                                elif language == 1:
                                        ch = "Compiling Kernel"
                        if what == 1:
                                if language == 0:
                                        ch = u"模块正在编译中"
                                elif language == 1:
                                        ch = "Compiling Module"
                        if what == 2:
                                ch = u"正在编译"
                        color = "yellow"
                elif status == "pass":
                        color = "green"
                        if what == 0:
                                if language == 0:
                                        ch = u"内核编译通过"
                                elif language == 1:
                                        ch = "Kernel Compile Pass"
                        if what == 1:
                                if language == 0:
                                        ch = u"模块编译通过"
                                elif language == 1:
                                        ch= "Module Compile Pass"
                        if what == 2:
                                if language == 0:
                                        ch = u"全部编译通过"
                                elif language == 1:
                                        ch = "All Compile Pass"
                elif status == "fail":
                        color = "red"
                        if what == 0:
                                if language == 0:
                                        ch = u"内核编译失败"
                                elif language == 1:
                                        ch = "Kernel Compile Failed"
                        if what == 1:
                                if language == 0:
                                        ch = u"模块编译失败"
                                elif language == 1:
                                        ch = "Module Compile Failed"
                elif status == "nothing":
                        color = "blue"
                        if what == 0:
                                if language == 0:
                                        ch = u"内核未编译"
                                elif language == 1:
                                        ch = "Kernel Not Compiled"
                        if what == 1:
                                if language == 0:
                                        ch = u"模块未编译"
                                elif language == 1:
                                        ch = "Module Not Compiled"

                self.status.setText(ch)
                self.palette.setColor(self.status.backgroundRole(),QColor("%s" %color))
                self.status.setPalette(self.palette)
        def onToolsClicked(self,name):
                row,col = self.getPosition(self.sender(),self.tools)
                if row == 0:
                        if self.sender().text() == self.toolnames[0][0]:
				if run_system == "Linux":
					what = 0
				elif run_system == "Windows":
					status = self.netclient.sendMessage("Kernel")
					if status == "running":
						self.status.setText(u"正在编译中")
					elif status == "ok":
						self.status.setText(u"编译通过")
					elif status == "fail":
						self.status.setText(u"编译失败")
                        elif self.sender().text() == self.toolnames[0][1]:
				if run_system == "Linux":
					what = 1
				elif run_system == "Windows":
					self.netclient.sendMessage("Module")
                        elif self.sender().text() == self.toolnames[0][2]:
				if run_system == "Linux":
					what = 2
				elif run_system == "Windows":
					self.netclient.sendMessage("All")
			if run_system == "Linux":
				print row,col
				runnable = Compiler(self.platform,self.kernel,self.module,self.toolchain,what)
				runnable.obj.compilerSignal.connect(self.slotTestSignal)
				self.tp.start(runnable)
                elif row == 1:
			files = []
			if col == 0:
				cmd = "get:kernel"
			elif col == 1:
				cmd = "get:module"
			elif col == 2:
				cmd = "get:all"
                        self.worker = ClientSend(self.netclient,cmd,col,self.out)
                        self.tp.start(self.worker)
                elif row == 2:
                        ok = self.db.open()
                        if ok:
                                query = QSqlQuery()
                                if col == 0:
                                        paths = self.default.keys()[:4]
                                        platforms = self.default.keys()[4:len(self.default)]
                                        for i in range(0,len(paths)):
                                                self.default[paths[i]] = self.path.itemAtPosition(i,1).widget().text()
                                        for i in range(0,len(platforms)):
                                                self.default[platforms[i]] = self.lists.itemAtPosition(0,i).widget().currentText()

                                        for key in self.default.keys():
                                                cmd = "update TSTools set path=\"%s\" where name=\"%s\"" %(self.default[key],key)
						print cmd
                                                query.exec_(cmd)
                                if col == 2:
                                        for key in self.default.keys():
                                                cmd = "update TSTools set path=\"""\" where name=\"%s\"" %(key)
                                                query.exec_(cmd)


        def onCurrentIndexChanged(self,name):
                row,col = self.getPosition(self.sender(),self.lists)
		if run_system == "Linux":
			if col == 0 :
				self.platform = self.sender().currentText()
				tmp = self.top + "/"+ self.sender().currentText()
				venders = os.listdir(tmp)
				self.lists.itemAtPosition(0,1).widget().clear()
				for v in venders:
					self.lists.itemAtPosition(0,1).widget().addItem(v)
			elif col == 1:
				vender = self.top+"/"+self.lists.itemAtPosition(0,0).widget().currentText()+"/"+self.sender().currentText()     
				versions = os.listdir(vender)
				self.lists.itemAtPosition(0,2).widget().clear()
				for v in versions:
					self.lists.itemAtPosition(0,2).widget().addItem(v)
			elif col == 2:
				self.kernel = self.top+"/"
				for i in range(0,3):
					if i == 0:
						self.platform = self.lists.itemAtPosition(0,i).widget().currentText()
					self.kernel += self.lists.itemAtPosition(0,i).widget().currentText()+"/"
		elif run_system == "Windows":
	        	if col == 0:
	        		self.platform = self.sender().currentText()
				reply = self.netclient.sendMessage("platform:"+"%s" %self.platform)
				if reply != "empty":
					self.lists.itemAtPosition(0,1).widget().clear()
					for vender in reply.split(":")[0:-1]:
						self.lists.itemAtPosition(0,1).widget().addItem(vender)
				else:
					self.lists.itemAtPosition(0,1).widget().clear()

			elif col == 1:
				self.vender = self.sender().currentText()
				reply = self.netclient.sendMessage("vender:"+"%s" %self.vender)
				print reply
				if reply != "empty":
					self.lists.itemAtPosition(0,2).widget().clear()
					self.lists.itemAtPosition(0,3).widget().clear()
					for version in reply.split(":")[0:-1]:
						if version.split("_")[0] == "Kernel":
							self.lists.itemAtPosition(0,2).widget().addItem(version)
						elif version.split("_")[0] == "Toolchain":
							self.lists.itemAtPosition(0,3).widget().addItem(version)
				else:
					self.lists.itemAtPosition(0,2).widget().clear()
					self.lists.itemAtPosition(0,3).widget().clear()

			elif col == 2:
				self.version = self.sender().currentText()
				reply = self.netclient.sendMessage("version:"+"%s" %self.version)
				if reply == "success":
					print "set kernel success"
			elif col == 3:
				self.toolchain = self.sender().currentText()
				reply = self.netclient.sendMessage("toolchain:"+"%s" %self.toolchain)
				if reply != "empty":
					self.path.itemAtPosition(3,1).widget().setText(reply)
				else:
					self.path.itemAtPosition(3,1).widget().clear()


        def getPosition(self,widget,grid):
                idx = grid.indexOf(widget)
                row,col = grid.getItemPosition(idx)[:2]
                return (row,col)

	def onConfigFileSelect(self):
		filename = self.sender().currentText()
		abspath = self.config_path+"/"+filename
		self.config_title.setText(abspath)
		fp = open(abspath,"w+")
		i = 1
		for line in fp.readlines():
			print line
			for j in range(0,3):
				if j == 0:
					item = QLabel(line.split(" ")[1])
				elif j == 1:
					item = QLineEdit(line.split(" ")[-1])
				elif j == 2:
					item = QPushButton(u"写入")

				self.configs.addWidget(item,i,j)
			i += 1
		       # for i in range(1,count):
		       # 	for j in range(0,3):
		       # 		if j == 0:
		       # 			item = QLabel(line.split(" ")[1])
		       # 		elif j == 1:
		       # 			item = QLineEdit(line.split(" ")[-1])	
		       # 		elif j == 2:
		       # 			item = QPushButton(u"写入")
		       # 			self.configs.addWidget(item,1,1)
		       # 		
                
	def configButtonClicked(self,name):
		row,col = self.getPosition(self.sender(),self.configs)
		if row == 0:
			fname = QFileDialog.getExistingDirectory(self,'Open file','/')
			self.config_path = fname
			self.configs.itemAtPosition(row,1).widget().clear()
			for f in os.listdir(fname):
				if f.split(".")[-1] == "h":
					self.configs.itemAtPosition(row,1).widget().addItem(f)
        def browseButtonClicked(self,name):
                button = self.sender()
                row,col = self.getPosition(button,self.path)
                if run_system == "Linux":
                        fname = QFileDialog.getExistingDirectory(self,'Open file','/')
                        self.path.itemAtPosition(row,1).widget().setText(fname)
                elif run_system == "Windows":
                        if row == 1 or row == 2:
				fname = QFileDialog.getExistingDirectory(self,'Open file','/')
				self.path.itemAtPosition(row,1).widget().setText(fname)
			elif row == 0:
				kernel = self.path.itemAtPosition(row,1).widget().text()
				if kernel == "":
					print "empty kernel directory"
				elif kernel.split("/")[-1] != "Kernels":
					print "invalid kernel directory"
				else:
					reply = self.netclient.sendMessage("kernel:"+"%s" %kernel)
					self.lists.itemAtPosition(0,0).widget().clear()
					for platform in reply.split(":")[0:-1]:
						self.lists.itemAtPosition(0,0).widget().addItem(platform)

def getLanguageType():
        ll=locale.getdefaultlocale()
        if ll[0] == "zh_CN":
                return 0
        elif ll[0] == "en_US":
                return 1
def main():
        app = QApplication(sys.argv)
        if(len(sys.argv) > 1):
                if sys.argv[1] == "-c":
                        T = TSTools(0)
                elif sys.argv[1] == "-s":
                        T = TSTools(1)
        else:
                T = TSTools(-1)
        sys.exit(app.exec_())
if __name__ == "__main__":
        language = getLanguageType()
        run_system = platform.system()
        main()
