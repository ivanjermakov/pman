import curses
from curses import window

import psutil as ps
from psutil import Process, NoSuchProcess

from pmn.abstract_process_view import AbstractProcessView
from pmn.info_format import InfoFormat
from pmn.search_view import SearchView
from pmn.status_view import StatusView


# we need to wrap it like that because calling `Process(pid)` immediately after calling `ps.pids()` can
# cause NoSuchProcess
def _get_process(pid):
    try:
        return Process(pid)
    except NoSuchProcess:
        return None


class ListProcessView(AbstractProcessView):
    def __init__(self, screen, config):
        super().__init__(screen)
        self.processes = None
        self.visible_processes = None
        self.layout = config.list_layout
        self.keymap = config.list_keymap
        self.pad: window = None
        self.status = StatusView(self.screen)
        self.search = SearchView(self.screen)
        self.search_string = None

        self.current_process_index = 0
        self.page_scroll_offset = 0

    def update_processes(self):
        self.processes = list(filter(
            lambda p: p and p.cmdline(),
            map(
                lambda pid: _get_process(pid),
                ps.pids()
            )
        ))
        self.visible_processes = self.search_processes(self.search_string)
        # in case cursor was further down the list than the list length itself
        if self.current_process_index > len(self.processes):
            self.last()

    def show(self):
        self.screen.refresh()
        h, w = self.screen.getmaxyx()

        self.update_processes()
        self.pad = curses.newpad(len(self.visible_processes) if self.visible_processes else 1, w)

        for i, p in enumerate(self.visible_processes):
            if p.is_running():
                self.print_process(p, i)

        self.pad.refresh(self.page_scroll_offset, 0, 0, 0, h - 1 - 1, w - 1)
        self.status.draw(f'{self.current_process_index + 1}/{len(self.visible_processes)}')
        if self.search_string is not None:
            self.search.draw(self.search_string)

    def loop(self):
        return self.keymap(self)

    def search_loop(self):
        curses.curs_set(1)
        if self.search_string is None:
            self.search_string = ''
        while True:
            self.first()
            self.screen.erase()
            self.show()
            search_key = self.screen.get_wch()
            if type(search_key) == int:
                continue
            elif ord(search_key) == 127:  # backspace
                self.search_string = self.search_string[:-1]
            elif search_key == '\n':  # enter
                curses.curs_set(0)
                break
            elif ord(search_key) == 27:  # escape
                self.clear_search()
                break
            elif ord(search_key) >= 32:
                self.search_string += search_key

    def clear_search(self):
        curses.curs_set(0)
        self.first()
        self.search_string = None
        self.screen.erase()
        self.visible_processes = self.processes
        self.show()

    def resize(self, h):
        new_h, new_w = self.screen.getmaxyx()
        delta_current = self.current_process_index - self.page_scroll_offset + 1
        if delta_current > h / 2:
            delta_h = h - new_h
            self.page_scroll_offset += delta_h
        self.screen.erase()

    def next(self):
        if self.current_process_index == len(self.visible_processes) - 1:
            return
        self.current_process_index += 1
        if self.current_process_index == self.page_scroll_offset + self.screen.getmaxyx()[0] - 1:
            self.page_scroll_offset += 1

    def prev(self):
        if self.current_process_index == 0:
            return
        self.current_process_index -= 1
        if self.current_process_index == self.page_scroll_offset - 1:
            self.page_scroll_offset -= 1

    def first(self):
        self.page_scroll_offset = 0
        self.current_process_index = 0

    def last(self):
        self.current_process_index = len(self.visible_processes) - 1
        self.page_scroll_offset = self.current_process_index - self.screen.getmaxyx()[0] + 2

    def print_process(self, process: Process, index):
        formats = self.layout(process)
        InfoFormat.print_formats(
            formats,
            self.screen.getmaxyx()[1],
            index,
            self.current_process_index,
            self.pad
        )

    def search_processes(self, search_string):
        if not search_string:
            return self.processes
        return list(filter(
            lambda p: search_string in ' '.join(p.cmdline()),
            self.processes
        ))
