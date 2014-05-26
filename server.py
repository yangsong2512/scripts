#!/usr/bin/python
import sys
import locale
import os
import collections
import time
import subprocess
import platform
import socket
import threading

class CommandHandler(threading.Thread):
	def __init__(self,client):
		threading.Thread.__init__(self)
		self.client = client
		self.kernel = ""
		self.module = "/opt/module/"
		self.out = ""
		self.toolchain = ""
	def run(self):
		client_quit = False
		##Here we will tell client a connection was established
		self.client.send("success")
		##Then we need client tell us more infomation about it
		info = self.client.recv(1024)
		ClientId = info.split(":")
		##Then we need create directory where our module will stay in
		if not os.path.exists(self.module):
			os.mkdir(self.module)
		self.module += "/%s" %ClientId[1]
		if not os.path.exists(self.module):
			os.mkdir(self.module)
		self.module += "/CN1100"
		if not os.path.exists(self.module):
			os.mkdir(self.module)

		##At last we enter a while loop to wait for command from client
		while not client_quit:
			message = self.client.recv(512)
			print message
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
			elif types[0] == "push":
				print types[1]
				if types[1] == "module":
					self.client.send("ready")
					self.recvFiles()
			elif types[0] == "compile":
				if types[1] == "kernel":
					what = 0
					if self.kernel == "" or self.toolchain == "":
						print "Kernel or Toolchain missed"
						self.client.send("fail")
					else:
						self.compiler(self.platform,self.kversion,self.module,self.toolchain,what)
				elif types[1] == "module":
					what = 1
					if self.kernel == "" or self.toolchain == "" or self.module == "":
						print "Kernel or Toolchain or Module missed"
						self.client.send("fail")
					else:
						self.compiler(self.platform,self.kversion,self.module,self.toolchain,what)
				elif types[1] == "all":
					what = 2
					if self.kernel == "" or self.toolchain == "" or self.module == "":
						print "Kernel or Toolchain or Module missed"
						self.client.send("fail")
					else:
						self.compiler(self.platform,self.kversion,self.module,self.toolchain,what)
			elif types[0] == "pull":
				images = []
				if types[1] == "kernel" or types[1] == "all":
					if self.platform == "Rockchip":
						images.append(self.kversion+"/kernel.img")
				if types[1] == "module" or types[1] == "all":
					images.append(self.module+"/cn1100_linux.ko")
				for i in range(0,len(images)):
					if os.path.exists(images[i]):
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
					else:
						self.client.send("miss:"+"%s" %types[1])
			elif message == "quit":
				client_quit = True
				self.client.close()
				break
	def compiler(self,platform,kernel,module,toolchain,what):
		print module
                if (what == 0 or what == 2) and (kernel != ""):
			if mutex.acquire(1):
				if platform == "Samsung":
					status = subprocess.call(["make","ARCH=arm","CROSS_COMPILE=%s" %self.toolchain,"-C","%s" %kernel,"zImage"])
				elif platform == "Rockchip":
					status = subprocess.call(["make","ARCH=arm","CROSS_COMPILE=%s" %self.toolchain,"-C","%s" %self.kversion,"kernel.img"])
				if not status:
					self.client.send("kernel:pass")
				else:
					self.client.send("kernel:fail")
				mutex.release()
                if (what == 1 or what == 2) and (module != ""):
                        status = subprocess.call(["make","CROSS_COMPILE=%s" %self.toolchain,"KERNEL=%s" %kernel,"MODULE=%s" %module,"-C","%s" %module])
			if not status:
				self.client.send("module:pass")
			else:
				self.client.send("module:fail")

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
	def removeDir(self,topdir):
		for root,dirs,files in os.walk(topdir,topdown=False):
			for name in files:
				os.remove(os.path.join(root,name))
			for name in dirs:
				os.rmdir(os.path.join(root,name))

mutex = threading.Lock()

class NetServer:
        def __init__(self,port):
		self.host = "192.168.1.103"
                self.port = port
		self.run()

        def run(self):
                self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server.bind((self.host,self.port))
                self.server.listen(5)
                while True:
			self.client,self.caddr = self.server.accept()
			thread = CommandHandler(self.client) 
			thread.start()

#        def quit(self):
#                self.app_closed = True
#                self.server.close()
#

if __name__ == "__main__":
	N = NetServer(1234)
