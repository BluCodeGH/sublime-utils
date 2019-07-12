import os
import subprocess
import sublime
import sublime_plugin

class SublimeFilesOpenCommand(sublime_plugin.WindowCommand):
  def __init__(self, *args):
    self.data = []
    self.folder = None
    self.active_view = None
    self.hidden = False
    super().__init__(*args)

  def run(self):
    self.active_view = self.window.active_view()
    self.navigate("~")

  def navigate(self, folder):
    self.window.show_quick_panel([], None)
    self.folder = os.path.abspath(os.path.expanduser(folder))
    self.data = ["[{}]".format(self.folder)]
    if not self.hidden:
      self.data.append(".*")
    if not os.path.samefile(self.folder, "/"):
      self.data.append("..")
    cmd = ["rg", "-u" if not self.hidden else "-uu", "--files", self.folder]
    #cmd = ["find", self.folder, "-mindepth", "1", "-type", "f"]
    process = subprocess.Popen(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
      self.data.extend([l[len(self.folder) + 1:] for l in process.communicate()[0].splitlines()])
    except:
      process.kill()
      process.wait()
      raise
    self.window.show_quick_panel(self.data, self.chosen, sublime.MONOSPACE_FONT, 1, self.preview)

  def chosen(self, i):
    if i < 1:
      self.window.focus_view(self.active_view)
      return
    if self.data[i] == ".*":
      self.hidden = True
      self.navigate(self.folder)
      return
    file = os.path.join(self.folder, self.data[i])
    if self.data[i] == "..":
      self.navigate(file)
      return
    self.window.open_file(file)

  def preview(self, i):
    if i < 2:
      return
    file = os.path.join(self.folder, self.data[i])
    if os.path.getsize(file) < 1e6:
      self.window.open_file(file, sublime.TRANSIENT)
    else:
      self.window.focus_view(self.active_view)

class SublimeFilesSaveCommand(sublime_plugin.TextCommand):
  def run(self, _):
    if self.view.file_name() is None:
      self.view.run_command("sublime_files_save_as")
    else:
      self.view.run_command("save")

class SublimeFilesSaveAsCommand(sublime_plugin.TextCommand):
  def __init__(self, *args):
    self.folder = None
    self.data = None
    self.preview = None
    super().__init__(*args)

  def run(self, _):
    blank = os.path.join(os.path.dirname(__file__))
    self.preview = self.view.window().open_file(blank)
    self.preview.set_scratch(True)
    self.navigate("~")

  def navigate(self, folder):
    self.view.window().show_quick_panel([], None)
    self.folder = os.path.abspath(os.path.expanduser(folder))
    self.data = ["[{}]".format(self.folder)]
    if not os.path.samefile(self.folder, "/"):
      self.data.append("..")
    self.data.append(".")
    cmd = ["find", self.folder, "-mindepth", "1", "-type", "d"]
    process = subprocess.Popen(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
      cut = len(self.folder)
      if self.folder[-1] != "/":
        cut += 1
      self.data.extend(["{}/".format(l[cut:]) for l in process.communicate()[0].splitlines()])
    except:
      process.kill()
      process.wait()
      raise
    self.view.window().show_quick_panel(self.data, self.chosen, sublime.MONOSPACE_FONT, 1, self.previewFolder)

  def previewFolder(self, i):
    if i < 1:
      self.preview.run_command("sublime_files_preview_folder", {"folder": None})
      return
    folder = os.path.join(self.folder, self.data[i])
    self.preview.run_command("sublime_files_preview_folder", {"folder": folder})

  def chosen(self, i):
    self.preview.close()
    self.view.window().focus_view(self.view)
    if i < 1:
      return
    if self.data[i] == "..":
      self.navigate(os.path.dirname(self.folder))
      return
    self.folder = os.path.join(self.folder, self.data[i])
    self.view.window().show_input_panel("Filename", self.folder, self.save, None, None)

  def save(self, file):
    self.view.retarget(os.path.join(self.folder, file))
    self.view.run_command("save")

class SublimeFilesPreviewFolderCommand(sublime_plugin.TextCommand):
  def run(self, edit, folder):
    if folder is None:
      self.view.erase(edit, sublime.Region(0, self.view.size()))
      return
    cmd = ["ls", "-1AF", folder]
    process = subprocess.Popen(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
      data = process.communicate()[0]
    except:
      process.kill()
      process.wait()
      raise
    self.view.erase(edit, sublime.Region(0, self.view.size()))
    self.view.insert(edit, 0, data)
