import os
import subprocess
import tempfile
import sublime
import sublime_plugin

class SublimeFilesOpenCommand(sublime_plugin.WindowCommand):
  def run(self):
    temp = os.path.join(tempfile.gettempdir(), next(tempfile._get_candidate_names()))
    fifo = None
    try:
      os.mkfifo(temp)
      fifo = os.open(temp, os.O_RDONLY | os.O_NONBLOCK)

      cmd = [
        "kitty", "--class", "popup", "-d", "~", "bash", "-c",
        "fzf --info=hidden --preview=\"less {} 2>/dev/null\" --preview-window=right:50% --bind \"enter:accept+execute(echo {} > " + temp + ")\""
      ]
      subprocess.Popen(cmd).wait()

      toOpen = os.read(fifo, 1024).decode()
      if toOpen:
        toOpen = os.path.join(os.path.expanduser("~"), toOpen[:-1])
        self.window.open_file(toOpen)
    finally:
      if fifo:
        os.close(fifo)
      os.remove(temp)

class SublimeFilesSaveCommand(sublime_plugin.TextCommand):
  def run(self, _):
    if self.view.file_name() is None: # the file has not been saved yet
      self.view.run_command("sublime_files_save_as")
    else:
      self.view.run_command("save")

class SublimeFilesSaveAsCommand(sublime_plugin.TextCommand):
  def run(self, _):
    temp = os.path.join(tempfile.gettempdir(), next(tempfile._get_candidate_names()))
    fifo = None
    try:
      os.mkfifo(temp)
      fifo = os.open(temp, os.O_RDONLY | os.O_NONBLOCK)

      cmd = [
        "kitty", "--class", "popup", "-d", "~", "bash", "-c",
        "fd -HI -t d -E \\.git | fzf --info=hidden --preview=\"/bin/ls ~/{} -AFh --color=always\" --preview-window=right:30% --bind \"enter:accept+execute(echo {} > " + temp + ")\""
      ]
      subprocess.Popen(cmd).wait()

      toSave = os.read(fifo, 1024).decode()
      if toSave:
        toSave = os.path.join(os.path.expanduser("~"), toSave[:-1]) + "/"
        self.view.window().show_input_panel("Save", toSave, self.save, None, None)
    finally:
      if fifo:
        os.close(fifo)
      os.remove(temp)

  # actually save
  def save(self, file):
    if os.path.exists(file):
      sublime.error_message("File {} already exists.".format(file))
      return
    self.view.retarget(file)
    self.view.run_command("save")
