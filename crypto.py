import base64
import functools
import os.path
import subprocess
import sublime
import sublime_plugin

class Crypto(sublime_plugin.ViewEventListener):
  def __init__(self, *args):
    super().__init__(*args)
    self.enabled = False # are we responding to events
    self.encrypted = True # is the current view encrypted
    self.passwordCache = None
    self.fname = None # used to detect renames / new files
    self.busy = False # currently editing the view so ignore on_modified
    self.activated = False # only trigger on_activated once
    self.locki = 0
    self.buf = ""
    self.prompti = 0

  def prompt(self, prompt, callback, verify=lambda p: True):
    self.enabled = False
    self.view.set_read_only(True)
    self.buf = ""
    self.prompti = 0
    context = (prompt, callback, verify)
    self.view.window().show_input_panel(
        prompt,
        "",
        functools.partial(self.verify, context, self.prompti),
        functools.partial(self.wip, context, self.prompti),
        functools.partial(self.verify, context, self.prompti)
    )

  def wip(self, context, prompti, password):
    if self.prompti != prompti:
      return
    old = len(self.buf)
    self.buf = self.buf[:len(password)]
    self.buf += password[len(self.buf):]
    if len(self.buf) != old:
      self.prompti += 1
      self.view.window().show_input_panel(
          context[0],
          "*" * len(password),
          functools.partial(self.verify, context, self.prompti),
          functools.partial(self.wip, context, self.prompti),
          functools.partial(self.verify, context, self.prompti)
      )

  def verify(self, context, prompti, _=None):
    if self.prompti != prompti:
      return
    self.view.set_read_only(False) # verify might need to edit
    password = self.buf
    _, callback, verify = context
    if not password:
      self.close()
    elif not verify(password):
      sublime.error_message("Invalid password.")
      self.prompt(*context)
    else:
      callback(password)
      self.enabled = True

  def close(self):
    print("Closing")
    self.view.window().focus_view(self.view)
    self.view.window().run_command('close_file')

  def on_activated(self):
    if self.activated:
      return
    self.activated = True
    fname = self.view.file_name()
    if fname is None or os.path.splitext(fname)[1] != ".enc":
      return
    print("activated")
    self.enabled = True
    self.fname = fname
    self.prompt("Enter password", self.setup, self.decrypt)

  def setup(self, password):
    print("setup")
    self.passwordCache = password

  def on_pre_save(self):
    fname = self.view.file_name()
    if fname != self.fname: # new file / save as
      if fname is None or os.path.splitext(fname)[1] != ".enc":
        self.enabled = False
        self.view.set_scratch(False)
        return
    if self.enabled and not self.encrypted:
      print("pre")
      self.encrypt()

  def on_post_save(self):
    if self.enabled and self.encrypted:
      print("post")
      self.decrypt()
    fname = self.view.file_name()
    if fname != self.fname: # new file / save as
      self.fname = fname
      if fname is None or os.path.splitext(fname)[1] != ".enc":
        return
      print("save as")
      self.prompt("Enter new password", self.setupEncrypt)

  def setupEncrypt(self, password):
    print("setup encrypt")
    self.passwordCache = password
    self.encrypted = False
    self.enabled = True
    self.view.run_command("save")

  def on_modified(self):
    if not self.enabled or self.busy:
      return
    self.locki = (self.locki + 1) % 65536
    sublime.set_timeout_async(functools.partial(self.lock, self.locki), 10*60*1000)
    self.view.set_scratch(False)

  def encrypt(self):
    print("encrypting")
    self.busy = True
    self.view.run_command("sublime_utils_encrypt", {"password": self.passwordCache})
    self.encrypted = True

  # decrypt, make it seem like file is unmodified
  def decrypt(self, password=None):
    print("decrypting")
    password = password or self.passwordCache
    self.busy = True
    sublime.set_timeout_async(self.not_busy, 100)
    self.view.run_command("sublime_utils_decrypt", {"password": password, "showErrors": False})
    if self.view.get_status("sublime_utils_decrypt_status") == "Failed":
      self.encrypted = True
      return False
    self.encrypted = False
    self.view.erase_status("sublime_utils_decrypt_status")
    self.view.reset_reference_document() # diff on left
    self.view.set_scratch(True) # no dirty flag in tab
    sublime.set_timeout_async(functools.partial(self.lock, self.locki), 10*60*1000)
    return True

  def lock(self, i):
    if i != self.locki or self.encrypted or not self.enabled or self.view.window() is None:
      return
    print("lock")
    self.view.run_command("save")
    self.encrypt()
    self.passwordCache = None
    self.prompt("Enter password", self.setup, self.decrypt)

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
