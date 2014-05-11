#!/usr/bin/python
#-*-coding:utf-8 -*-
import sys
import os
import collections
import time
import subprocess
import platform
import socket
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4.QtSql import *


global run_system

class SignalObject(QObject):
	compilerSignal = pyqtSignal(str,int)
	networkSignal = pyqtSignal(str)

class NetServer(QRunnable):
	def __init__(self,port):
		QRunnable.__init__(self)
		self.obj = SignalObject()
		self.host = socket.gethostname()
		self.port = port
		self.app_closed = False
	def run(self):
		self.server = socket.socket()
		self.server.bind((self.host,self.port))
		self.server.listen(5)
		while True:
			if self.app_closed:
				break
			self.client,self.caddr = self.server.accept()
			print "Get connection from :",self.caddr
			self.client.send("Connect success")
			self.client.close()
	def quit(self):
		self.app_closed = True
		self.stop()
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

	def closeEvent(self,event):
		print "APP will be closed"
		self.netserver.quit()

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
		self.labels=[u"内核路径",u"模块路径",u"输出路径",u"编译工具"]
		self.toolnames = [[u"编译内核",u"编译模块",u"编译全部"],[u"输出内核",u"输出模块",u"输出全部"],\
				[u"保存参数","",u"重置参数"]]

		self.tp = QThreadPool()

		if self.toolsType == 1:
			print "initial server"
			self.netserver = NetServer(1234)
			self.netserver.obj.networkSignal.connect(self.onNetWork)
			self.tp.start(self.netserver)
		elif self.toolsType == 2:
			self.netclient = NetClient(1234)
			self.netclient.obj.networkSignal.connect(self.onNetWork)
			self.tp.start(self.netclient)

		fbox = QHBoxLayout()


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
			for j in range(0,3):
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
					wg.textChanged.connect(self.textChanged)
				if j == 2:
					if run_system == "Linux":
						wg = QPushButton(u"浏览")
					elif run_system == "Windows":
						wg = QPushButton(u"设置")
					wg.clicked.connect(self.browseButtonClicked)
				self.path.addWidget(wg,i,j)

		paths = self.default.keys()[:4]
		for i in range(0,len(paths)):
			self.path.itemAtPosition(i,1).widget().setText(self.default[paths[i]])

		vbox = QVBoxLayout()
		vbox.addLayout(self.path)
		vbox.addLayout(self.lists)
		vbox.addLayout(self.tools)
		
		self.setLayout(vbox)
		self.setWindowTitle(u"内核编译")
		self.show()


	def onNetWork(self):
		pass

	def textChanged(self,text):
		lineEdit = self.sender()
		row,col = self.getPosition(lineEdit,self.path)
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

	def slotTestSignal(self,status,what):
		if status == "running":
			if what == 0:
				ch = u"内核正在编译中"
			if what == 1:
				ch = u"模块正在编译中"
			if what == 2:
				ch = u"正在编译"
			color = "yellow"
		elif status == "pass":
			color = "green"
			if what == 0:
				ch = u"内核编译通过"
			if what == 1:
				ch = u"模块编译通过"
			if what == 2:
				ch = u"全部编译通过"
		elif status == "fail":
			color = "red"
			if what == 0:
				ch = u"内核编译失败"
			if what == 1:
				ch = u"模块编译失败"
		elif status == "nothing":
			color = "blue"
			if what == 0:
				ch = u"内核未编译"
			if what == 1:
				ch = u"模块未编译"

		self.status.setText(ch)
		self.palette.setColor(self.status.backgroundRole(),QColor("%s" %color))
		self.status.setPalette(self.palette)
	def onToolsClicked(self,name):
		row,col = self.getPosition(self.sender(),self.tools)
		if row == 0:
			if self.sender().text() == self.toolnames[0][0]:
				what = 0
			elif self.sender().text() == self.toolnames[0][1]:
				what = 1
			elif self.sender().text() == self.toolnames[0][2]:
				what = 2
			print row,col
			runnable = Compiler(self.platform,self.kernel,self.module,self.toolchain,what)
			runnable.obj.compilerSignal.connect(self.slotTestSignal)
			self.tp.start(runnable)
		elif row == 1:
			pass
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
						query.exec_(cmd)
				if col == 2:
					for key in self.default.keys():
						cmd = "update TSTools set path=\"""\" where name=\"%s\"" %(key)
						query.exec_(cmd)


	def onCurrentIndexChanged(self,name):
		row,col = self.getPosition(self.sender(),self.lists)
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

	def getPosition(self,widget,grid):
		idx = grid.indexOf(widget)
		row,col = grid.getItemPosition(idx)[:2]
		return (row,col)
		
	def browseButtonClicked(self,name):
		button = self.sender()
		row,col = self.getPosition(button,self.path)
		if run_system == "Linux":
			fname = QFileDialog.getExistingDirectory(self,'Open file','/')
			self.path.itemAtPosition(row,1).widget().setText(fname)
		elif run_system == "Windows":
			keys = self.default.keys()[:4]
			self.default[keys[row]]
			print self.default[keys[row]]
			
def main():

	app = QApplication(sys.argv)
	if len(sys.argv) < 2:
		return
	if sys.argv[1] == "-c":
		T = TSTools(0)
	elif sys.argv[1] == "-s":
		T = TSTools(1)
	else:
		T = TSTools(-1)
	sys.exit(app.exec_())
if __name__ == "__main__":
	run_system = platform.system()
	main()



