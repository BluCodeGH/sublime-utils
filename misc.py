import re
import sublime
import sublime_plugin

class DetectIndentation(sublime_plugin.ViewEventListener):
  def on_load_async(self):
    self.view.run_command("detect_indentation", {"threshold": 2})

class AlignCursorsCommand(sublime_plugin.TextCommand):
  def run(self, _):
    col = self.view.rowcol(self.view.sel()[0].a)[1]
    res = []
    for region in self.view.sel():
      row = self.view.rowcol(region.a)[0]
      line = self.view.line(region.a)
      line_length = line.b - line.a
      new = self.view.text_point(row, min(line_length, col))
      res.append(sublime.Region(new, new))
    self.view.sel().clear()
    self.view.sel().add_all(res)

class IncrementCommand(sublime_plugin.TextCommand):
  def run(self, _):
    if len(self.view.sel()) > 1:
      return
    def perform(iter_max):
      self.view.run_command("perform_increment", {"iter_max": int(iter_max)})
    self.view.window().show_input_panel("Increment", "", perform, None, None)

class PerformIncrementCommand(sublime_plugin.TextCommand):
  def run(self, edit, iter_max):
    if len(self.view.sel()) > 1:
      return
    text = self.view.substr(self.view.sel()[0])
    if text[0] != "\n" and text[-1] != "\n":
      text = "\n" + text
    matches = []
    for match in re.finditer(r"-?\d+", text):
      matches.append((match.span(), int(text[match.start():match.end()])))
    point = max(self.view.sel()[0].a, self.view.sel()[0].b)
    for i in range(1, iter_max):
      res = text
      for (start, stop), j in reversed(matches):
        res = res[:start] + str(i + j) + res[stop:]
      point += self.view.insert(edit, point, res)
