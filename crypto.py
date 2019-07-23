import base64
import os.path
import subprocess
import sublime
import sublime_plugin

class Crypto(sublime_plugin.ViewEventListener):
  def __init__(self, *args):
    super().__init__(*args)
    self.password = None
    self.fname = None
    self.busy = False

  # view gains focus, we use to detect opening and decrypt
  def on_activated(self):
    fname = self.view.file_name()
    if fname is None or os.path.splitext(fname)[1] != ".enc" or self.fname:
      return
    self.fname = fname
    self.view.window().show_input_panel("Enter password", "", self.setup, None, self.close)

  # encrypt before save
  def on_pre_save(self):
    fname = self.view.file_name()
    if fname is None or os.path.splitext(fname)[1] != ".enc":
      return
    if fname != self.fname: # this was a save as / new file
      self.fname = True
      self.view.window().show_input_panel("Enter new password", "", self.setupEncrypt, None, self.setupEncrypt)
      return
    self.encrypt()

  # decrypt after save
  def on_post_save(self):
    fname = self.view.file_name()
    if fname is None or os.path.splitext(fname)[1] != ".enc" or not self.password:
      return
    if self.fname is True: # coming out of a new file / save as so dont decrypt
      self.fname = fname
      return
    self.decrypt()

  # reset scratch so dirty flag appears
  def on_modified(self):
    fname = self.view.file_name()
    if fname is None or os.path.splitext(fname)[1] != ".enc" or self.busy:
      return
    self.view.set_scratch(False)

  def setup(self, password):
    self.password = password
    self.decrypt()

  def setupEncrypt(self, password=None):
    if not password:
      sublime.error_message("Password cannot be blank.")
    else:
      self.password = password
    self.view.run_command("save")

  def encrypt(self):
    self.busy = True # dont let on_modified reset dirty flag
    self.view.run_command("sublime_utils_encrypt", {"password": self.password})

  # decrypt, make it seem like file is unmodified
  def decrypt(self):
    self.busy = True # dont let on_modified reset dirty flag
    self.view.run_command("sublime_utils_decrypt", {"password": self.password})
    if self.view.get_status("sublime_utils_decrypt_status") == "Failed":
      self.view.close()
      return
    self.view.erase_status("sublime_utils_decrypt_status")
    self.view.reset_reference_document() # diff on left
    self.view.set_scratch(True) # no dirty flag in tab
    sublime.set_timeout_async(self.not_busy, 100) # timeout to enable on_modified

  def close(self):
    self.view.close()

  def not_busy(self):
    self.busy = False

class SublimeUtilsEncryptCommand(sublime_plugin.TextCommand):
  def run(self, edit, password):
    plaintext = self.view.substr(sublime.Region(0, self.view.size()))
    cmd = ["gpg", "-c", "--batch", "--passphrase", password]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
      ciphertext, errs = process.communicate(input=plaintext.encode())
      retcode = process.returncode
    except:
      process.kill()
      process.wait()
      raise
    if errs:
      sublime.error_message("Encryption failed with code {}:\n{}".format(retcode, errs.decode()))
      return
    self.view.replace(edit, sublime.Region(0, self.view.size()), base64.b64encode(ciphertext, b"+\n").decode())

class SublimeUtilsDecryptCommand(sublime_plugin.TextCommand):
  def run(self, edit, password):
    ciphertext = base64.b64decode(self.view.substr(sublime.Region(0, self.view.size())), b"+\n")
    cmd = ["gpg", "-d", "-q", "--batch", "--passphrase", password]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
      plaintext, errs = process.communicate(input=ciphertext)
      retcode = process.returncode
    except:
      process.kill()
      process.wait()
      raise
    if errs:
      self.view.set_status("sublime_utils_decrypt_status", "Failed")
      sublime.error_message("Decryption failed with code {}:\n{}".format(retcode, errs.decode()))
      return
    self.view.set_status("sublime_utils_decrypt_status", "Success")
    self.view.replace(edit, sublime.Region(0, self.view.size()), plaintext.decode())
