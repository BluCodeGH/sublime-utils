import functools
import os
import subprocess
import sublime
import sublime_plugin

class SublimeFilesOpenCommand(sublime_plugin.WindowCommand):
  def __init__(self, *args):
    super().__init__(*args)
    self.active_view = None
    self.hidden = False

  def run(self):
    self.active_view = self.window.active_view()
    self.hidden = False
    self.navigate("~")

  def navigate(self, folder):
    self.window.show_quick_panel([], None)
    folder = os.path.abspath(os.path.expanduser(folder))
    data = ["[{}]".format(folder)]
    if not self.hidden:
      data.append(".*")
    if not os.path.samefile(folder, "/"):
      data.append("..")
    cmd = ["rg", "-u" if not self.hidden else "-uu", "--files", folder]
    #cmd = ["find", folder, "-mindepth", "1", "-type", "f"]
    process = subprocess.Popen(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
      cut = len(folder)
      if folder[-1] != "/":
        cut += 1
      data.extend([l[cut:] for l in process.communicate()[0].splitlines()])
    except:
      process.kill()
      process.wait()
      raise
    self.window.show_quick_panel(data, functools.partial(self.chosen, folder, data), sublime.MONOSPACE_FONT, 1, functools.partial(self.preview, folder, data))

  def chosen(self, folder, data, i):
    if i < 1:
      self.window.focus_view(self.active_view)
      return
    if data[i] == ".*":
      self.hidden = True
      self.navigate(folder)
      return
    file = os.path.join(folder, data[i])
    if data[i] == "..":
      self.navigate(file)
      return
    self.window.open_file(file)

  def preview(self, folder, data, i):
    if i < 1 or data[i] in ["..", ".*"]:
      self.window.focus_view(self.active_view)
      return
    file = os.path.join(folder, data[i])
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
    super().__init__(*args)
    self.preview = None

  def run(self, _):
    blank = os.path.join(os.path.dirname(__file__))
    self.preview = self.view.window().open_file(blank)
    self.preview.set_scratch(True)
    self.navigate("~")

  def navigate(self, folder):
    self.view.window().show_quick_panel([], None)
    folder = os.path.abspath(os.path.expanduser(folder))
    data = ["[{}]".format(folder)]
    if not os.path.samefile(folder, "/"):
      data.append("..")
    data.append(".")
    cmd = ["find", folder, "-mindepth", "1", "-type", "d"]
    process = subprocess.Popen(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
      cut = len(folder)
      if folder[-1] != "/":
        cut += 1
      data.extend(["{}/".format(l[cut:]) for l in process.communicate()[0].splitlines()])
    except:
      process.kill()
      process.wait()
      raise
    self.view.window().show_quick_panel(data, functools.partial(self.chosen, folder, data), sublime.MONOSPACE_FONT, 1, functools.partial(self.previewFolder, folder, data))

  def previewFolder(self, folder, data, i):
    if i < 1:
      self.preview.run_command("sublime_files_preview_folder", {"folder": None})
      return
    folder = os.path.join(folder, data[i])
    self.preview.run_command("sublime_files_preview_folder", {"folder": folder})

  def chosen(self, folder, data, i):
    self.preview.close()
    self.view.window().focus_view(self.view)
    if i < 1:
      return
    if data[i] == "..":
      self.navigate(os.path.dirname(folder))
      return
    folder = os.path.join(folder, data[i])
    self.view.window().show_input_panel("Filename", folder, self.save, None, None)

  def save(self, file):
    self.view.retarget(file)
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
