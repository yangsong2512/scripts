#!/usr/bin/python
#-*-coding:utf-8 -*-
import sys
import locale
import string
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
from struct import *


global run_system
global language
global frame

def getFormatTime(fmt):
	curtime = time.strftime("%s" %fmt,time.localtime())
	return curtime

class SignalObject(QObject):
        compilerSignal = pyqtSignal(str,int)
        networkSignal = pyqtSignal(str,int)

class ClientSend(QRunnable):
	def __init__(self,client):
		QRunnable.__init__(self)
		self.obj = SignalObject()
		self.client = client
	def setArgs(self,message,num,arg):
		self.message = message
		self.col = num
		self.out = arg
	def sendMessage(self,message):
		self.client.client.send(message)
		return self.client.client.recv(512)

	def genLinuxDir(self,lists):
		target = ""
		index = 0
		for i in range(0,len(lists)):
			if lists[i] == "CN1100":
				index = i
				break
		for i in range(index+1,len(lists)):	
			target += lists[i]+"/"

		return target
	def sendDir(self,topdir):
		dirlist = os.listdir(topdir)
		for f in dirlist:
			curdir = topdir+"\\"+f
			print curdir
			if os.path.isdir(curdir):
				senddir = self.genLinuxDir((curdir).split("\\"))
				tmp = "D:"+senddir
				reply = self.sendMessage(tmp)
				self.sendDir(curdir)
			elif os.path.isfile(curdir):
				sendfile = self.genLinuxDir((curdir).split("\\"))[:-1]
				reply = self.sendMessage("F:"+sendfile)
				if reply == "sReady":
					fp = open(curdir,"rb")
					while True:
					       buf = fp.read(1024)
					       if not buf:
						       reply = self.sendMessage("over")
						       break;
					       reply = self.sendMessage(buf)
	def run(self):
		cmd = self.message.split(":")
		if cmd[0] == "pull":
			files = []
			self.client.client.send("%s" %self.message)
			if self.col == 0 or self.col == 2:
				filename = "%s" %self.out+"\\"+"kernel_"+getFormatTime("%m%d%H%M")+"_%s" %cmd[2]+".img"
				files.append(filename)
			if self.col == 1 or self.col == 2:
				filename = "%s" %self.out+"\\"+"cn1100_linux_"+getFormatTime("%m%d%H%M")+".ko"
				files.append(filename)
			print files
			status = True
			for i in range(0,len(files)):
				self.obj.networkSignal.emit(self.message+":running",-1)
				fp = open(files[i],"wb+")
				while True:
					buf = self.client.client.recv(1024)
					self.client.client.send("success")
					if buf == "complete":
						if self.col != 2:
							self.obj.networkSignal.emit(self.message+":ok",-1)
							break
						else:
							break
					elif buf.split(":")[0] == "miss":
						if self.col != 2:
							self.obj.networkSignal.emit(self.message+":miss",-1)
							break
						else:
							status = False
							break
					else:
						fp.write(buf)
			if self.col == 2:
				if not status:
					self.obj.networkSignal.emit(self.message+":miss",-1)
				else:
					self.obj.networkSignal.emit(self.message+":ok",-1)
		elif cmd[0] == "push":
			if cmd[1] == "module":
				self.obj.networkSignal.emit(self.message+":running",-1)
				reply = self.sendMessage(self.message)
				self.sendDir(self.out)	
				self.sendMessage("complete")
				self.obj.networkSignal.emit(self.message+":ok",-1)
		elif cmd[0] == "compile":
			if cmd[1] == "all":
				lists = ["compile:kernel","compile:module"]
				for i in range(0,len(lists)):
					self.obj.networkSignal.emit(lists[i]+":running",self.col)
					self.client.client.send("%s" %lists[i])
					reply = self.client.client.recv(512)
					self.obj.networkSignal.emit("compile:"+reply,self.col)
			else:
				self.obj.networkSignal.emit(self.message+":running",self.col)
				self.client.client.send("%s" %self.message)
				reply = self.client.client.recv(512)
				self.obj.networkSignal.emit("compile:"+reply,self.col)
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
                self.host = "192.168.1.103"
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
						for name in os.listdir(tmp)[0].split("-")[0:-1]:
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

##Main Class
class TSTools(QWidget):
        def __init__(self,s):
                super(TSTools,self).__init__()
                self.toolsType = s
                self.top = ""
                self.module = ""
                self.out = ""
                self.toolchain = ""
		frame = 300
                self.default = collections.OrderedDict([("kernel",""),("module",""),("out",""),\
                                ("toolchain",""),("platform",""),("vender",""),("version",""),("toolchain_version",""),("resolution","")])
                self.palette = QPalette()
                self.initDB()           
                self.initUI()

	##generate linux directory,so server can recognize
	def genLinuxDir(self,lists):
		target = ""
		for i in range(2,len(lists)):
			target += lists[i]+"/"

		return target


	##send directory fucntion
	##1.list all files in current directory
	##2.judge whether file is directory or file
	##3.if is directory then recall the function
	##4.if is file,then send file
	##5.recv will block,so we used it to sync
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

	##this was called when window was closed
        def closeEvent(self,event):
                print "APP will be closed"
                if self.toolsType == 1:
                        self.netserver.quit()
		elif self.toolsType == 0:
			self.netclient.sendMessage("quit")

	##connect to data base
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

        def initUI(self):
                if language == 0:
                        self.labels=[u"内核路径",u"模块路径",u"输出路径",u"编译工具"]
                        self.toolnames = [[u"编译内核",u"编译模块",u"编译全部"],[u"输出内核",u"输出模块",u"输出全部"],\
                                        [u"保存参数",u"更新源码",u"重置参数"]]
                elif language == 1:
                        self.labels=["Top Dir","Module Dir","Out Dir","Tool Dir"]
                        self.toolnames = [["Compile Kernel","Compile Module","Compile All"],["Output Kernel","Output Module","Output All"],\
                                        ["Save Paths","","Reset Paths"]]

                self.tp = QThreadPool()

		self.tab_widget = QTabWidget()
		self.tab_widget.currentChanged[int].connect(self.onTabChanged)
		tab1 = QWidget()
		tab2 = QScrollArea()
		tab2.setWidget(QWidget())
		tab3 = QScrollArea()
		tab3.setWidget(QWidget())
		
		self.tab1_layout = QVBoxLayout(tab1)
		self.tab2_layout = QVBoxLayout(tab2.widget())
		tab2.setWidgetResizable(True)
		self.tab3_layout = QVBoxLayout(tab3.widget())
		tab3.setWidgetResizable(True)

		self.tab_widget.addTab(tab1,u"内核编译")
		self.tab_widget.addTab(tab2,u"驱动配置")
		self.tab_widget.addTab(tab3,u"数据显示")

                self.tools = QGridLayout()
                for i in range(0,len(self.toolnames)):
                        for j in range(0,len(self.toolnames[0])):
                                tl = QPushButton(self.toolnames[i][j])
                                tl.clicked.connect(self.onToolsClicked)
				self.tools.addWidget(tl,i,j)

                self.lists = QGridLayout()
                for i in range(0,1):
                        for j in range(0,5):
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
                                                wg.textChanged[str].connect(self.onTextChanged)
                                        elif run_system == "Windows":
						wg.textChanged[str].connect(self.onTextChanged)
                                if j == 2:
                                        if run_system == "Linux":
                                                wg = QPushButton(u"浏览")
                                        elif run_system == "Windows":
						if i == 1 or i == 2:
							wg = QPushButton(u"浏览")
						else:
							wg = QPushButton(u"设置")
                                        wg.clicked.connect(self.onBrowseButtonClicked)
                                self.path.addWidget(wg,i,j)

		self.status = QLineEdit(u"编译状态")

                ##Initialize network here
                if self.toolsType == 1:
                        print "initial server"
                        self.netserver = NetServer(1234)
                        self.tp.start(self.netserver)
                elif self.toolsType == 0:
                        self.netclient = NetClient("192.168.1.106",1234,self.tp)
			self.worker = ClientSend(self.netclient)
			self.worker.obj.networkSignal.connect(self.onParseResult)
                        status = self.netclient.connect()
			if status:
				info = platform.uname()
				details = ""
				for i in range(0,len(info)):
					details += info[i]+":"
				self.netclient.client.send(details)
				ch = u"成功连接服务器"
				color = "green"
				self.status.setText(ch)
				self.palette.setColor(self.status.backgroundRole(),QColor("%s" %color))
				self.status.setPalette(self.palette)


		##we first read path from database and save them to dictionary self.default
		##and here we read from this dictionary and set it as default value
                paths = self.default.keys()[:4]
                for i in range(0,len(paths)):
			value = self.default[paths[i]]
			if value != "":
				self.path.itemAtPosition(i,1).widget().setText(value)

		plats = self.default.keys()[4:]
		for i in range(0,len(plats)):
			value = self.default[plats[i]]
			if value != "":
				item_found = False
				tmp = self.lists.itemAtPosition(0,i).widget()
				if tmp.count() == 0:
					tmp.addItem(value)
				else:
					for j in range(0,tmp.count()):
						if tmp.itemText(j) == value:
							item_found = True
							tmp.setCurrentIndex(j)
							break
					if not item_found:
						tmp.addItem(value)
						tmp.setCurrentIndex(tmp.count()-1)



		self.initConfig()
		self.initData()

                mainlayout = QVBoxLayout()
                self.tab1_layout.addLayout(self.path)
                self.tab1_layout.addLayout(self.lists)
                self.tab1_layout.addLayout(self.tools)
		self.tab1_layout.addWidget(self.status)
		mainlayout.addWidget(self.tab_widget)
                
                self.setLayout(mainlayout)
		self.setWindowTitle(u"驱动编译与调试")
                self.show()

	def readFile(self):
		for i in range(0,3):
			count = 0
			matrix = unpack("300h",self.logData.read(150*4))
			if i == 0:
				for j in range(0,15):
					for k in range(0,10):
						self.rawLayout.itemAtPosition(j,k).widget().setText("%d" %matrix[count])
						count += 1
			if i == 1:
				for j in range(0,15):
					for k in range(0,10):
						self.baseLayout.itemAtPosition(j,k).widget().setText("%d" %matrix[count])
						count += 1
			if i == 2:
				for j in range(0,15):
					for k in range(0,10):
						self.diffLayout.itemAtPosition(j,k).widget().setText("%d" %matrix[count])
						count += 1

	def onLogSelect(self):
		if self.sender() == self.logSelect:
			fname = QFileDialog.getOpenFileName(self,'Open file','/')
			self.logPath.setText(fname)
			if fname != "":
				self.logData = open(fname,"rb")
				self.readFile()
		elif self.sender() == self.nextbutton:
			self.readFile()
		elif self.sender() == self.prebutton:
			self.logData.seek(-600*3*2,1)
			self.readFile()
		elif self.sender() == self.resetbutton:
			self.logData.seek(0,0)
			self.readFile()

		elif self.sender() == self.jumpbutton:
			text, ok = QInputDialog.getText(self, u"跳转至",u"帧数:")
			if ok:
				num = int(text)
				self.logData.seek(600*3*num,0)
				self.readFile()
		

	def initData(self):
		vbox = QVBoxLayout()
		hbox = QHBoxLayout()
		headbox = QHBoxLayout()
		rawGroup = QGroupBox(u"原始数据")
		diffGroup = QGroupBox(u"差分数据")
		baseGroup = QGroupBox(u"基准数据")

		buttonbox = QHBoxLayout()
		self.nextbutton = QPushButton(u"下一帧")
		self.nextbutton.clicked.connect(self.onLogSelect)
		buttonbox.addWidget(self.nextbutton)
		self.prebutton = QPushButton(u"上一帧")
		self.prebutton.clicked.connect(self.onLogSelect)
		buttonbox.addWidget(self.prebutton)
		self.resetbutton = QPushButton(u"复位")
		self.resetbutton.clicked.connect(self.onLogSelect)
		buttonbox.addWidget(self.resetbutton)
		self.jumpbutton = QPushButton(u"跳转至")
		self.jumpbutton.clicked.connect(self.onLogSelect)
		buttonbox.addWidget(self.jumpbutton)
		buttonbox.addStretch(1)
		
		self.logPath = QLineEdit()
		headbox.addWidget(self.logPath)
		self.logSelect = QPushButton(u"浏览")
		headbox.addWidget(self.logSelect)
		self.logSelect.clicked.connect(self.onLogSelect)
		headbox.addStretch(1)
		
		self.rawLayout = QGridLayout()
		for i in range(0,15):
			for j in range(0,10):
				item = QLabel("1000")
				self.rawLayout.addWidget(item,i,j)
		rawGroup.setLayout(self.rawLayout)

		self.diffLayout = QGridLayout()
		for i in range(0,15):
			for j in range(0,10):
				item = QLabel("1000")
				self.diffLayout.addWidget(item,i,j)
		diffGroup.setLayout(self.diffLayout)
		self.baseLayout = QGridLayout()
		for i in range(0,15):
			for j in range(0,10):
				item = QLabel("1000")
				self.baseLayout.addWidget(item,i,j)
		baseGroup.setLayout(self.baseLayout)
		hbox.addWidget(rawGroup)
		hbox.addWidget(baseGroup)
		hbox.addWidget(diffGroup)
		vbox.addLayout(headbox)
		vbox.addLayout(hbox)
		vbox.addLayout(buttonbox)
		self.tab3_layout.addLayout(vbox)
	def initConfig(self):
		self.config_path = ""
		hbox = QHBoxLayout()
		name = QLabel(u"当前头文件")
		self.config_title = QLineEdit()
		self.config_title.setReadOnly(True)
		hbox.addWidget(name)
		hbox.addWidget(self.config_title)

		self.infos = QGridLayout()
		for i in range(0,1):
			for j in range(0,4):
				if j == 0:
					item = QLabel(u"头文件路径")
				if j == 1:
					item = QLineEdit()
					item.setReadOnly(True)
				if j == 2:
					item = QComboBox()
					item.currentIndexChanged.connect(self.onConfigFileSelect)
					item.setMinimumWidth(150)
				if j == 3:
					item = QPushButton(u"浏览")
					item.clicked.connect(self.onConfigButtonClicked)

				item.setMinimumHeight(25)
				self.infos.addWidget(item,i,j)

		self.configs = QGridLayout()
		
		saveBox = QHBoxLayout()
		saveBox.addStretch(1)
		self.saveButton = QPushButton(u"保存")
		saveBox.addWidget(self.saveButton)
		self.saveButton.clicked.connect(self.onConfigButtonClicked)
		self.checkAll = QCheckBox()
		self.checkAll.stateChanged[int].connect(self.onCheckBoxStateChanged)
		saveBox.addWidget(self.checkAll)

		vbox = QVBoxLayout()
		vbox.addLayout(hbox)
		vbox.addLayout(self.infos)
		vbox.addLayout(self.configs)
		vbox.addLayout(saveBox)
		self.tab2_layout.addLayout(vbox)

	def setStatusPrompt(self,text,color):	
		self.status.setText(text)
		self.palette.setColor(self.status.backgroundRole(),QColor("%s" %color))
		self.status.setPalette(self.palette)

	def onCheckBoxStateChanged(self,text):
		row_count = 0
		if self.sender() == self.checkAll:
			row_count = self.configs.count()/3
			checked = self.sender().isChecked()
			for i in range(0,row_count):
				item = self.configs.itemAtPosition(i,2).widget()
				if checked:
					item.setChecked(True)
				else:
					item.setChecked(False)
				
		else:
			row,col = self.getPosition(self.sender(),self.configs)
			key = self.configs.itemAtPosition(row,0).widget().text()
			value = self.configs.itemAtPosition(row,1).widget().text()
			if self.sender().isChecked():
				self.updates["%s" %key] ="%s" %value
			else:
				if key in self.updates.keys():
					del self.updates["%s" %key]

	def onTabChanged(self,index):
		if index == 2:
			pass

        def onReturnPressed(self):
                lineEdit = self.sender()
                row,col = self.getPosition(lineEdit,self.path)
		keys = self.default.keys()
		self.netclient.sendMessage(keys[row]+":"+self.sender().text())


        def onTextChanged(self,text):
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
			if row == 0:
				kernel = lineEdit.text()
				if kernel.split("/")[-1] == "Kernels":
					reply = self.netclient.sendMessage("kernel:"+"%s" %kernel)
			elif row == 1:
				pass
			elif row == 2:
				self.out = lineEdit.text()

        def onParseResult(self,status,what):
		tmp = status.split(":")
		ch = ""
		color = ""
		if tmp[0] == "pull":
			if tmp[1] == "kernel" :
				if tmp[-1] == "ok":
					if language == 0:
						ch = u"成功下载内核镜像"
						color = "green"
				elif tmp[-1] == "miss":
					if language == 0:
						ch = u"找不到内核镜像"
						color = "red"
				elif tmp[-1] == "running":
					if language == 0:
						ch = u"正在下载内核镜像"
						color = "yellow"

			if tmp[1] == "module" :
				if tmp[-1] == "ok":
					if language == 0:
						ch = u"成功下载驱动模块"
						color = "green"
				elif tmp[-1] == "miss":
					if language == 0:
						ch = u"找不到驱动模块"
						color = "red"
				elif tmp[-1] == "running":
					if language == 0:
						ch = u"正在下载驱动模块"
						color = "yellow"
			if tmp[1] == "all":
				if tmp[-1] == "ok":
					if language == 0:
						ch = u"镜像下载成功"
						color = "green"
				elif tmp[-1] == "miss":
					if language == 0:
						ch = u"内核或者模块缺失"
						color = "red"
				elif tmp[-1] == "running":
					if language == 0:
						ch = u"正在下载镜像"
						color = "yellow"

                elif tmp[0] == "compile":
			if tmp[1] == "kernel":
				if tmp[-1] == "pass":
					color = "green"
					if language == 0:
						ch = u"内核编译通过"
					elif language == 1:
						ch = "Kernel Compile Pass"
				elif tmp[-1] == "fail":
					color = "red"
					if language == 0:
						ch = u"内核编译失败"
					elif language == 1:
						ch = "Kernel Compile Failed"
				elif tmp[-1] == "running":
					color = "yellow"
					if language == 0:
						ch = u"内核正在编译中"
					elif language == 1:
						ch = "Compiling Kernel"

			elif tmp[1] == "module":
				if tmp[2] == "pass":
					color = "green"
					if language == 0:
						ch = u"模块编译通过"
					elif language == 1:
						ch= "Module Compile Pass"
				elif tmp[2] == "fail":
					color = "red"
					if language == 0:
						ch = u"模块编译失败"
					elif language == 1:
						ch = "Module Compile Failed"
				elif tmp[2] == "running":
					color = "yellow"
					if language == 0:
						ch = u"模块正在编译中"
					elif language == 1:
						ch = "Compiling Module"


                elif tmp[0] == "push":
			if tmp[1] == "module": 
				print tmp[2]
				if tmp[2] == "running":
					color = "yellow"
					if language == 0:
						ch = u"正在上传源码"
					elif language == 1:
						ch = "Kernel Not Compiled"
				if tmp[2] == "ok":
					color = "green"
					if language == 0:
						ch = u"源码上传成功"
					elif language == 1:
						ch = "Module Not Compiled"

                self.status.setText(ch)
                self.palette.setColor(self.status.backgroundRole(),QColor("%s" %color))
                self.status.setPalette(self.palette)
        def onToolsClicked(self,name):
                row,col = self.getPosition(self.sender(),self.tools)
                if row == 0:
                        if self.sender().text() == self.toolnames[0][0]:
				what = 0
				if run_system == "Windows":
					cmd = "compile:kernel"
                        elif self.sender().text() == self.toolnames[0][1]:
				what = 1
				if run_system == "Windows":
					cmd = "compile:module"
                        elif self.sender().text() == self.toolnames[0][2]:
				what = 2
				if run_system == "Windows":
					cmd = "compile:all"
			if run_system == "Windows":
				self.worker = ClientSend(self.netclient)
				self.worker.obj.networkSignal.connect(self.onParseResult)
				self.worker.setArgs(cmd,what,self.out)
				self.tp.start(self.worker)
			if run_system == "Linux":
				runnable = Compiler(self.platform,self.kernel,self.module,self.toolchain,what)
				runnable.obj.compilerSignal.connect(self.onParseResult)
				self.tp.start(runnable)
                elif row == 1:
			files = []
			resolution = self.lists.itemAtPosition(0,4).widget().currentText()
			if col == 0:
				cmd = "pull:kernel:%s" %resolution
			elif col == 1:
				cmd = "pull:module:%s" %resolution
			elif col == 2:
				cmd = "pull:all:%s" %resolution
                        self.worker = ClientSend(self.netclient)
			self.worker.obj.networkSignal.connect(self.onParseResult)
			self.worker.setArgs(cmd,col,self.out)
                        self.tp.start(self.worker)
                elif row == 2:
			if col == 0 or col == 2:
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
							query.exec_(cmd)
					if col == 2:
						for key in self.default.keys():
							cmd = "update TSTools set path=\"""\" where name=\"%s\"" %(key)
							query.exec_(cmd)
			elif col == 1:
				cmd = "push:module"
				self.module = self.path.itemAtPosition(1,1).widget().text()
				self.worker = ClientSend(self.netclient)
				self.worker.obj.networkSignal.connect(self.onParseResult)
				self.worker.setArgs(cmd,-1,self.module)
				self.tp.start(self.worker)

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
				print reply
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
				print reply
				if reply == "success":
					if self.platform == "Rockchip":
						##util above codes default value has been set,so use a function may be a better way
						##resolution was not read from files,so we add two default here
						##and it maybe changed with default values
						fp = open("TSTools.cfg","rb")
						for line in fp.readlines():
							if line.split()[0] == "resolution":
								resolutions = line.split()[1:]
								resolution = self.lists.itemAtPosition(0,4).widget()
								if resolution.count() == 0:
									for i in range(0,len(resolutions)):
										resolution.addItem(resolutions[i])
								else:
									for i in range(0,len(resolutions)):
										item_found = False
										for j in range(0,resolution.count()):
											if resolution.itemText(j) == resolutions[i]:
												item_found = True
												break
										if not item_found:
											resolution.addItem(resolutions[i])	
			elif col == 3:
				self.toolchain = self.sender().currentText()
				reply = self.netclient.sendMessage("toolchain:"+"%s" %self.toolchain)
				if reply != "empty":
					self.path.itemAtPosition(3,1).widget().setText(reply)
				else:
					self.path.itemAtPosition(3,1).widget().clear()
			elif col == 4:
				if self.sender().currentText() != "":
					self.netclient.client.send("config:resolution:"+"%s" %self.sender().currentText())
					reply = self.netclient.client.recv(512)
					status = reply.split(":")
					if status[0] == "fail":
						if status[1] == "kernel":
							self.setStatusPrompt(u"内核没有设置","red")
						elif status[2] == "config_file":
							self.setStatusPrompt(u"未找到配置文件","red")
					elif status[0] == "success":
						self.setStatusPrompt(u"成功设置内核配置文件:%s" %status[1],"green")



        def getPosition(self,widget,grid):
                idx = grid.indexOf(widget)
                row,col = grid.getItemPosition(idx)[:2]
                return (row,col)


	def addItemToConfigs(self,line,row):
	        for i in range(0,3):
	        	if i == 0:
	        		item = QLabel(line.split()[1])
				item.setMinimumHeight(25)
	        	elif i == 1:
	        		item = QLineEdit(line.split()[2])
				item.setMinimumHeight(25)
			elif i == 2:
				item = QCheckBox()
				item.stateChanged[int].connect(self.onCheckBoxStateChanged)
	        	self.configs.addWidget(item,row,i)
	def parseHeader(self,contents,direct):
		if direct == 1:
			keys = self.updates.keys()
		else_block = []
		row_count = 0
		block = []
		defines = []
		handled = []
		for line in contents:
			if len(line.split()) > 0:
				tmp = line.split()
				line = ""
				for i in range(0,len(tmp)):
					line += tmp[i] + " "
				line += "\n"
				if line.split()[0][0:2] == "\\" or line.split()[0][0:2] == "\*":
					continue
				elif line.split()[0] == "#ifndef":
					block.append({0:True})

				elif line.split()[0] == "#ifdef":
					key = block[-1].keys()[0]
					value = block[-1][key]
					if len(else_block) == 0:
						if value:
							if line.split()[1] in defines:
								block.append({(key+1):True})
							else:
								block.append({(key+1):False})
						else:
							block.append({(key+1):False})
					elif else_block[-1] == -1:
						block.append({(key+1):False})
					elif else_block[-1] == 1:
						if line.split()[1] in defines:
							block.append({(key+1):True})
						else:
							block.append({(key+1):False})

				elif line.split()[0] == "#else":
					key = block[-1].keys()[0]
					value = block[-1][key]
					count = len(else_block)
					if count == 0:
						if key == 1:
							if value:
								else_block.append(-1)
							else:
								else_block.append(1)
						elif key > 1:
							keytmp = block[-2].keys()[0]
							valuetmp = block[-2][keytmp]
							if valuetmp:
								if value:
									else_block.append(-1)
								else:
									else_block.append(1)
							else:
								else_block.append(-1)
					elif count > 0:
						if else_block[-1] == 1:
							if value:
								else_block.append(-1)
							else:
								else_block.append(1)
						elif else_block[-1] == -1:
							else_block.append(-1)
				elif line.split()[0] == "#define":
					key = block[-1].keys()[0]
					value = block[-1][key]
					if key == 0:
						if len(line.split()) == 2:
							defines.append(line.split()[1])
						elif len(line.split()) > 2:
							if line.split()[2][0:2] == "\\":
								defines.append(line.split()[1])
							else:
								if direct == 0:
									self.addItemToConfigs(line,row_count)
									row_count += 1
								elif direct == 1:
									tmpkey = line.split()[1]
									if tmpkey in keys:
										tmp = line.split()
										line = ""
										tmp[2] = self.updates[tmpkey]
										for i in range(0,len(tmp)):
											line += tmp[i] + " "
										line+="\n"
					elif key > 0 and len(line.split()) > 2:
						if value:
							if direct == 0:
								self.addItemToConfigs(line,row_count)
								row_count += 1
							elif direct == 1:
								tmpkey = line.split()[1]
								if tmpkey in keys:
									tmp = line.split()
									line = ""
									tmp[2] = self.updates[tmpkey]
									for i in range(0,len(tmp)):
										line += tmp[i] + " "
									line+="\n"
						else:
							if len(else_block) > 0:
								if else_block[-1] == 1:
									if direct == 0:
										self.addItemToConfigs(line,row_count)
										row_count += 1
									elif direct == 1:
										tmpkey = line.split()[1]
										if tmpkey in keys:
											tmp = line.split()
											line = ""
											tmp[2] = self.updates[tmpkey]
											for i in range(0,len(tmp)):
												line += tmp[i] + " "
											line+="\n"


				elif line.split()[0] == "#if":
					key = block[-1].keys()[0]
					value = block[-1][key]
					if value:
						if line.split()[1] == "1":
							block.append({(key+1):True})
						else:
							block.append({(key+1):False})
					else:
						tmpkey = block[-2].keys()[0]
						tmpvalue = block[-2][key]
						if else_block[-1] == 1:
							if line.split()[1] == "1":
								block.append({(key+1):True})
							else:
								block.append({(key+1):False})
						else:
							block.append({(key+1):False})


				elif line.split()[0] == "#endif":
					if len(else_block) > 0:
						else_block.pop()
					block.pop()
				handled.append("%s" %line)

		if direct == 1:
			fp = open(self.config_file,"w+")
			for line in handled:
				fp.write(line)

			fp.close()


	def onConfigFileSelect(self):
		for i in reversed(range(self.configs.count())):
			self.configs.itemAt(i).widget().setParent(None)
		filename = self.sender().currentText()
		self.config_file = self.config_path+"\\"+filename
		self.config_title.setText(self.config_file)
		if self.config_file.split(".")[-1] == "h":
			self.updates = {}
			fp = open(self.config_file,"rb")
			self.contents = fp.readlines()
			self.parseHeader(self.contents,0)
			fp.close()
                
	def onConfigButtonClicked(self,name):
		if self.sender() == self.saveButton:
			keys = self.updates.keys()
			if len(keys) > 0:
				self.parseHeader(self.contents,1)
		else:
			row,col = self.getPosition(self.sender(),self.infos)
			if row == 0:
				fname = QFileDialog.getExistingDirectory(self,'Open file','/')
				self.config_path = fname
				self.infos.itemAtPosition(row,1).widget().setText(self.config_path)
				self.infos.itemAtPosition(row,2).widget().clear()
				for f in os.listdir(fname):
					if f.split(".")[-1] == "h":
						self.infos.itemAtPosition(row,2).widget().addItem(f)
        def onBrowseButtonClicked(self,name):
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
		if run_system == "Windows":
			T = TSTools(0)
		else:
			T = TSTools(-1)
        sys.exit(app.exec_())
if __name__ == "__main__":
        language = getLanguageType()
        run_system = platform.system()
	computer_name = platform.uname()[1]
        main()
