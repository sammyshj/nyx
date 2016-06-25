"""
Panel providing raw control port access with syntax hilighting, usage
information, tab completion, and other usability features.
"""

import nyx.controller
import nyx.curses
import re

from nyx.curses import BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, BOLD, HIGHLIGHT, NORMAL
from nyx import panel, tor_interpreter

import stem.connection
import stem.interpreter.commands


USAGE_INFO = 'to use this panel press enter'
PROMPT = '>>> '
PROMPT_LINE = [[(PROMPT, GREEN, BOLD), (USAGE_INFO, CYAN, BOLD)]]
ANSI_RE = re.compile("\\x1b\[([0-9;]*)m")
ATTRS = {"0": NORMAL, "1": BOLD, "30": BLACK, "31": RED, "32": GREEN, "33": YELLOW, "34": BLUE, "35": MAGENTA, "36": CYAN}

def ansi_to_output(line, attrs):
  ansi_re = ANSI_RE.findall(line)
  new_attrs = []

  if line.find("\x1b[") == 0 and ansi_re:
    for attr in ansi_re[0].split(';'):
      new_attrs.append(ATTRS[attr])
    attrs = new_attrs
  line = ANSI_RE.sub('', line)

  return [(line, ) + tuple(attrs)], attrs


class InterpreterPanel(panel.Panel):
  """
  Renders the interpreter panel with a prompt providing raw control port
  access.
  """

  def __init__(self):
    panel.Panel.__init__(self, 'interpreter')

    self._is_input_mode = False
    self._x_offset = 0
    self._scroller = nyx.curses.Scroller()
    self.controller = stem.connection.connect(
      control_port = ('127.0.0.1', 'default'),
      control_socket = '/var/run/tor/control',
      password_prompt = True,
    )
    self.interpreter = stem.interpreter.commands.ControlInterpretor(self.controller)

  def key_handlers(self):
    def _scroll(key):
      page_height = self.get_preferred_size()[0]
      is_changed = self._scroller.handle_key(key, len(PROMPT_LINE), page_height)

      if is_changed:
        self.redraw(True)

    def _execute_command():
      self._is_input_mode = True

      while self._is_input_mode:
        self.redraw(True)
        page_height = self.get_preferred_size()[0] - 1
        user_input = nyx.curses.str_input(len(PROMPT) + self._x_offset, self.top + len(PROMPT_LINE[-page_height:]))
        user_input, is_done = user_input.strip(), False

        if not user_input:
          is_done = True

        response = self.interpreter.run_command(user_input)
        color = None
        if response:
          PROMPT_LINE.insert(len(PROMPT_LINE) - 1, [(PROMPT, GREEN, BOLD), (user_input)])
          attrs = []
          for line in response.split('\n'):
            line, attrs = ansi_to_output(line, attrs)
            PROMPT_LINE.insert(len(PROMPT_LINE) - 1, line)

        if is_done:
          self._is_input_mode = False
          self.redraw(True)

    return (
      nyx.panel.KeyHandler('enter', 'execute a command', _execute_command, key_func = lambda key: key.is_selection()),
      nyx.panel.KeyHandler('arrows', 'scroll up and down', _scroll, key_func = lambda key: key.is_scroll()),
    )

  def draw(self, width, height):
    scroll = self._scroller.location(len(PROMPT_LINE), height)

    usage_msg = ' (enter \"/help\" for usage or a blank line to stop)' if self._is_input_mode else ""
    self.addstr(0, 0, 'Control Interpreter%s:' % usage_msg, HIGHLIGHT)

    is_scrollbar_visible = len(PROMPT_LINE) > height - 1
    if is_scrollbar_visible:
      self.add_scroll_bar(scroll, scroll + height, len(PROMPT_LINE), 1)

    self._x_offset, draw_line = 2 if is_scrollbar_visible else 0, 1 - scroll
    for entry in PROMPT_LINE:
      cursor = self._x_offset

      for line in entry:
        if len(line) == 1:
          self.addstr(draw_line, cursor, line[0])
        elif len(line) == 2:
          self.addstr(draw_line, cursor, line[0], line[1])
        elif len(line) == 3:
          self.addstr(draw_line, cursor, line[0], line[1], line[2])
        self.addstr(draw_line, cursor, line)
        try:
          cursor += len(line[0])
        except:
          pass

      draw_line += 1