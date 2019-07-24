import base64
import os.path
import subprocess
import sublime
import sublime_plugin

class Crypto(sublime_plugin.ViewEventListener):
  def __init__(self, *args):
    super().__init__(*args)
    self.enabled = False
    self.encrypted = True
    self.passwordCache = None
    self.fname = None
    self.busy = False
    self.activating = False

  def on_activated(self):
    if not self.encrypted or self.activating:
      return
    fname = self.view.file_name()
    if fname is None or os.path.splitext(fname)[1] != ".enc":
      self.encrypted = False
      return
    print("activated")
    self.view.set_read_only(True)
    self.activating = True
    self.view.window().show_input_panel("Enter password", "", self.setup, None, self.disable)

  def on_pre_save(self):
    fname = self.view.file_name()
    if fname != self.fname: # new file / save as
      if fname is None or os.path.splitext(fname)[1] != ".enc":
        return
      print("saveas")
      self.view.window().show_input_panel("Enter new password", "", self.setup, None, self.disable)
    elif self.enabled and not self.encrypted:
      print("pre")
      self.encrypt()

  def on_post_save(self):
    if not self.enabled:
      return
    print("post")
    if self.encrypted:
      self.decrypt()

  def on_modified(self):
    if not self.enabled or self.busy:
      return
    self.view.set_scratch(False)

  def setup(self, password):
    self.passwordCache = password
    self.fname = self.view.file_name()
    self.enabled = True
    self.view.set_read_only(False)
    if self.encrypted:
      self.activating = False
      if not self.decrypt():
        self.view.set_read_only(True)
        self.disable()
        self.activating = True
        self.view.window().show_input_panel("Enter password", "", self.setup, None, self.disable)
    else:
      if self.passwordCache:
        self.view.run_command("save") # encrypt
        self.activating = False
      else:
        sublime.error_message("Invalid password.")
        self.view.window().show_input_panel("Enter new password", "", self.setup, None, self.disable)

  def disable(self):
    print("disable")
    self.enabled = False
    self.fname = None
    self.passwordCache = None
    self.activating = False

  def encrypt(self):
    print("encrypting")
    self.busy = True
    self.view.run_command("sublime_utils_encrypt", {"password": self.passwordCache})
    self.encrypted = True

  # decrypt, make it seem like file is unmodified
  def decrypt(self):
    print("decrypting")
    self.busy = True
    sublime.set_timeout_async(self.not_busy, 100)
    self.view.run_command("sublime_utils_decrypt", {"password": self.passwordCache, "showErrors": False})
    if self.view.get_status("sublime_utils_decrypt_status") == "Failed":
      self.encrypted = True
      sublime.error_message("Invalid password.")
      return False
    self.encrypted = False
    self.view.erase_status("sublime_utils_decrypt_status")
    self.view.reset_reference_document() # diff on left
    self.view.set_scratch(True) # no dirty flag in tab
    return True

  def not_busy(self):
    self.busy = False


class SublimeUtilsEncryptCommand(sublime_plugin.TextCommand):
  def run(self, edit, password, showErrors=True):
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
      if showErrors:
        sublime.error_message("Encryption failed with code {}:\n{}".format(retcode, errs.decode()))
      return
    self.view.replace(edit, sublime.Region(0, self.view.size()), base64.b64encode(ciphertext, b"+\n").decode())

class SublimeUtilsDecryptCommand(sublime_plugin.TextCommand):
  def run(self, edit, password, showErrors=True):
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
      if showErrors:
        sublime.error_message("Decryption failed with code {}:\n{}".format(retcode, errs.decode()))
      return
    self.view.set_status("sublime_utils_decrypt_status", "Success")
    self.view.replace(edit, sublime.Region(0, self.view.size()), plaintext.decode())
