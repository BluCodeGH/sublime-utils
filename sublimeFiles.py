import functools
import os
import subprocess
import sublime
import sublime_plugin

class SublimeFilesOpenCommand(sublime_plugin.WindowCommand):
  def __init__(self, *args):
    super().__init__(*args)
    self.active_view = None # the original view we can use to hide transient previews
    self.hidden = False # show hidden files?

  def run(self):
    self.active_view = self.window.active_view()
    self.hidden = False
    self.navigate("~")

  # generate a list of all the files in a given directory
  def navigate(self, folder):
    self.window.show_quick_panel([], None) # clear any existing quick panels
    folder = os.path.abspath(os.path.expanduser(folder))
    data = ["[{}]".format(folder)] # title of the current directory
    if not self.hidden:
      data.append(".*") # option to show hidden files
    if not os.path.samefile(folder, "/"):
      data.append("..") # option to go one folder up
    cmd = ["rg", "-u" if not self.hidden else "-uu", "--files", folder] # use ripgrep to list files
    #cmd = ["find", folder, "-mindepth", "1", "-type", "f"]
    process = subprocess.Popen(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
      cut = len(folder)
      if folder[-1] != "/": # don't cut the first letter of paths after /
        cut += 1
      data.extend([l[cut:] for l in process.communicate()[0].splitlines()])
    except:
      process.kill()
      process.wait()
      raise
    # show quick panel, passing the folder and data to callbacks
    self.window.show_quick_panel(data, functools.partial(self.chosen, folder, data), sublime.MONOSPACE_FONT, 1, functools.partial(self.preview, folder, data))

  # the user presses enter on an item or cancels (i=-1)
  def chosen(self, folder, data, i):
    if i < 1:
      self.window.focus_view(self.active_view) # hide the transient preview
      return
    if data[i] == ".*":
      self.hidden = True
      self.navigate(folder) # redisplay the current folder with hidden files shown
      return
    file = os.path.join(folder, data[i])
    if data[i] == "..":
      self.navigate(file)
      return
    self.window.open_file(file)

  # a new quick panel item is highlighted
  def preview(self, folder, data, i):
    if i < 1 or data[i] in ["..", ".*"]:
      self.window.focus_view(self.active_view) # hide the transient preview
      return
    file = os.path.join(folder, data[i])
    if os.path.getsize(file) < 1e6: # the file is small enough to load quickly
      self.window.open_file(file, sublime.TRANSIENT) # show a transient (no tab) preview
    else:
      self.window.focus_view(self.active_view) # hide the transient preview

class SublimeFilesSaveCommand(sublime_plugin.TextCommand):
  def run(self, _):
    if self.view.file_name() is None: # the file has not been saved yet
      self.view.run_command("sublime_files_save_as")
    else:
      self.view.run_command("save")

class SublimeFilesSaveAsCommand(sublime_plugin.TextCommand):
  def __init__(self, *args):
    super().__init__(*args)
    self.preview = None # a view that will be used to list the contents of chosen directories

  def run(self, _):
    blank = os.path.join(os.path.dirname(__file__))
    self.preview = self.view.window().open_file(blank) # setup the preview view
    self.preview.set_scratch(True) # dont mark as dirty
    self.navigate("~")

  # list all folders in a directory
  def navigate(self, folder):
    self.view.window().show_quick_panel([], None) # hide existing quick panel
    folder = os.path.abspath(os.path.expanduser(folder))
    data = ["[{}]".format(folder)] # title of the current directory
    if not os.path.samefile(folder, "/"):
      data.append("..") # option to go up a directory
    data.append(".") # save in current folder
    cmd = ["find", folder, "-mindepth", "1", "-type", "d"] # list all directories recursively
    process = subprocess.Popen(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
      cut = len(folder)
      if folder[-1] != "/": # don't cut the first letter of paths after /
        cut += 1
      data.extend(["{}/".format(l[cut:]) for l in process.communicate()[0].splitlines()])
    except:
      process.kill()
      process.wait()
      raise
    # show quick panel to choose folder to save in
    self.view.window().show_quick_panel(data, functools.partial(self.chosen, folder, data), sublime.MONOSPACE_FONT, 1, functools.partial(self.previewFolder, folder, data))

  # list the contents of a folder in the preview view via the sublime_files_preview_folder command
  def previewFolder(self, folder, data, i):
    if i < 1:
      self.preview.run_command("sublime_files_preview_folder", {"folder": None})
      return
    folder = os.path.join(folder, data[i])
    self.preview.run_command("sublime_files_preview_folder", {"folder": folder})

  # prompt for the filename
  def chosen(self, folder, data, i):
    self.preview.close()
    self.view.window().focus_view(self.view) # focus original view
    if i < 1:
      return
    if data[i] == "..":
      self.navigate(os.path.dirname(folder))
      return
    folder = os.path.join(folder, data[i])
    # prompt for the filename, but allow editing the whole path
    self.view.window().show_input_panel("Filename", folder, self.save, None, None)

  # actually save
  def save(self, file):
    self.view.retarget(file)
    self.view.run_command("save")

# list the contents of a folder. This needs to be a separate command so we can use the passed `edit` to make changes to a view.
class SublimeFilesPreviewFolderCommand(sublime_plugin.TextCommand):
  def run(self, edit, folder):
    if folder is None:
      self.view.erase(edit, sublime.Region(0, self.view.size())) # just empty, dont write anything
      return
    cmd = ["ls", "-1AF", folder] # output directly written to preview buffer
    process = subprocess.Popen(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
      data = process.communicate()[0]
    except:
      process.kill()
      process.wait()
      raise
    self.view.erase(edit, sublime.Region(0, self.view.size()))
    self.view.insert(edit, 0, data)
