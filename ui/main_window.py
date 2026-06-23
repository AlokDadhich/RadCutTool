"""
RadCutTool — Main Window
Full Python/tkinter translation of the updated MATLAB RadCutTool.m

Key behaviours (from updated MATLAB):
  • On file load: reads actual angular extent and uses it everywhere
  • Theta quick-add buttons are rebuilt from actual grid range
  • Theta cuts outside grid range show a warning and are rejected
  • Grid range label shows "Grid range: 0 to X.X deg" live
  • interp2 orientation fix carried through in cut_engine
  • Phi / Theta / Both cut modes with sub-tab switching in Individual view
  • Overlay and Individual plot tabs
  • Export PNG dialog (overlay or per-cut)
  • Scrollable cut lists with scroll-wheel support
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from parser.grd_parser import parse_grd_all
from engine.cut_engine import phi_cut, theta_cut, grid_r_max

# ── Colour palette (matches MATLAB) ────────────────────────────────────────
CUT_COLORS = [
    '#4C9BE8', '#E8634C', '#F0A500', '#9B7FD4', '#4CAF7D',
    '#00BCD4', '#E91E8C', '#8BC34A', '#FF7043', '#78909C',
]

BG_DARK   = '#1A1E24'
BG_PANEL  = '#22272E'
BG_INPUT  = '#2C3240'
ACCENT    = '#4C9BE8'
DANGER    = '#E05252'
TEXT_PRI  = '#DDE3EC'
TEXT_SEC  = '#7A8594'
DIVIDER   = '#2C3240'
AXIS_BG   = '#FAFBFC'
GRID_CLR  = '#E4E8EE'

SB_W      = 260
N_POINTS  = 2000
ROW_H     = 28
CUT_LIST_H = 176


class RadCutApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title('RadCutTool - Radiation Pattern Analyzer')
        self.root.configure(bg=BG_DARK)
        self.root.geometry('1440x980')
        self.root.minsize(900, 600)

        # ── App state ──────────────────────────────────────────────────────
        self.all_freq_data   = []
        self.freq_labels     = []
        self.freq_values     = []
        self.current_freq    = 0       # index
        self.cuts            = []      # phi angles
        self.theta_cuts      = []      # theta angles
        self.active_tab      = 'overlay'
        self.cut_mode        = 1       # 1=phi, 2=theta, 3=both
        self.ind_sub_mode    = 1       # 1=phi rows, 2=theta rows

        self.grid_range_max  = float('inf')
        self.grid_phi_range_x = float('inf')
        self.grid_phi_range_y = float('inf')

        self._build_ui()
        self._apply_mode_visibility()

    # ══════════════════════════════════════════════════════════════════════
    #  UI BUILD
    # ══════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        root = self.root

        # ── Menu ──────────────────────────────────────────────────────────
        menubar = tk.Menu(root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label='Open .grd file...', command=self._cb_load)
        file_menu.add_separator()
        file_menu.add_command(label='Export PNG...', command=self._cb_export_dialog)
        file_menu.add_separator()
        file_menu.add_command(label='Exit', command=root.destroy)
        menubar.add_cascade(label='File', menu=file_menu)
        root.config(menu=menubar)

        # ── Top-level panes ────────────────────────────────────────────────
        self.pane = tk.PanedWindow(root, orient=tk.HORIZONTAL,
                                   sashwidth=4, bg=BG_DARK, bd=0)
        self.pane.pack(fill=tk.BOTH, expand=True)

        # Left sidebar
        self.sidebar = tk.Frame(self.pane, bg=BG_DARK, width=SB_W)
        self.sidebar.pack_propagate(False)
        self.pane.add(self.sidebar, minsize=SB_W, width=SB_W)

        # Right plot area
        self.plot_frame = tk.Frame(self.pane, bg='#F5F6F8')
        self.pane.add(self.plot_frame, minsize=400)

        self._build_sidebar()
        self._build_plot_area()

        root.bind('<MouseWheel>', self._cb_scroll_wheel)
        root.bind('<Button-4>',   self._cb_scroll_wheel)
        root.bind('<Button-5>',   self._cb_scroll_wheel)

    # ── Sidebar ────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        sb = self.sidebar

        # Scrollable sidebar container
        self._sb_canvas = tk.Canvas(sb, bg=BG_DARK, highlightthickness=0)
        self._sb_vsb    = tk.Scrollbar(sb, orient=tk.VERTICAL,
                                        command=self._sb_canvas.yview)
        self._sb_canvas.configure(yscrollcommand=self._sb_vsb.set)
        self._sb_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._sb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._sb_inner = tk.Frame(self._sb_canvas, bg=BG_DARK, width=SB_W-18)
        self._sb_win   = self._sb_canvas.create_window(
            (0, 0), window=self._sb_inner, anchor='nw')

        self._sb_inner.bind('<Configure>', self._on_sb_configure)
        self._sb_canvas.bind('<Configure>', self._on_sb_canvas_configure)

        c = self._sb_inner

        # Header
        hdr = tk.Frame(c, bg=BG_PANEL)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text='RadCutTool', font=('Arial', 13, 'bold'),
                 fg=TEXT_PRI, bg=BG_PANEL, anchor='w').pack(
                 fill=tk.X, padx=12, pady=(10, 0))
        tk.Label(hdr, text='Radiation Pattern Analyzer', font=('Arial', 8),
                 fg=TEXT_SEC, bg=BG_PANEL, anchor='w').pack(
                 fill=tk.X, padx=12, pady=(0, 10))

        # DATA FILE
        self._mk_hdr(c, 'DATA FILE')
        self.file_label = tk.Label(c, text='No file loaded', font=('Arial', 8),
                                   fg=TEXT_SEC, bg=BG_DARK, anchor='w', wraplength=220)
        self.file_label.pack(fill=tk.X, padx=12, pady=(2, 0))
        self._mk_btn(c, 'Open .grd File', self._cb_load, ACCENT, 'white')

        # FREQUENCY
        self._mk_hdr(c, 'FREQUENCY')
        tk.Label(c, text='Select block:', font=('Arial', 8),
                 fg=TEXT_SEC, bg=BG_DARK, anchor='w').pack(
                 fill=tk.X, padx=12)

        fl_frame = tk.Frame(c, bg=BG_DARK)
        fl_frame.pack(fill=tk.X, padx=12, pady=2)
        self.freq_listbox = tk.Listbox(fl_frame, height=4, font=('Courier', 8),
                                        fg=TEXT_PRI, bg=BG_INPUT,
                                        selectbackground=ACCENT,
                                        selectforeground='white',
                                        activestyle='none', bd=0,
                                        highlightthickness=0)
        self.freq_listbox.pack(fill=tk.X)
        self.freq_listbox.insert(tk.END, 'Load a .grd file first')
        self.freq_listbox.config(state=tk.DISABLED)
        self.freq_listbox.bind('<<ListboxSelect>>', self._cb_freq_select)

        freq_row = tk.Frame(c, bg=BG_DARK)
        freq_row.pack(fill=tk.X, padx=12, pady=2)
        tk.Label(freq_row, text='Label (GHz):', font=('Arial', 8),
                 fg=TEXT_SEC, bg=BG_DARK).pack(side=tk.LEFT)
        self.freq_entry = tk.Entry(freq_row, width=8, font=('Courier', 8),
                                    fg=TEXT_PRI, bg=BG_INPUT,
                                    insertbackground=TEXT_PRI, bd=0)
        self.freq_entry.pack(side=tk.LEFT, padx=4)
        self.freq_entry.bind('<Return>', self._cb_freq_label)
        tk.Button(freq_row, text='Set', font=('Arial', 8),
                  fg='white', bg=ACCENT, relief=tk.FLAT, bd=0,
                  command=self._cb_freq_label).pack(side=tk.LEFT)

        # CUT MODE
        self._mk_hdr(c, 'CUT MODE')
        mode_row = tk.Frame(c, bg=BG_DARK)
        mode_row.pack(fill=tk.X, padx=12, pady=2)
        self._mode_phi_btn   = tk.Button(mode_row, text='Phi cuts',
                                          font=('Arial', 8), relief=tk.FLAT, bd=0,
                                          command=lambda: self._cb_set_mode(1))
        self._mode_theta_btn = tk.Button(mode_row, text='Theta cuts',
                                          font=('Arial', 8), relief=tk.FLAT, bd=0,
                                          command=lambda: self._cb_set_mode(2))
        self._mode_both_btn  = tk.Button(mode_row, text='Both',
                                          font=('Arial', 8), relief=tk.FLAT, bd=0,
                                          command=lambda: self._cb_set_mode(3))
        for btn in (self._mode_phi_btn, self._mode_theta_btn, self._mode_both_btn):
            btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        # ── PHI CUTS section ──────────────────────────────────────────────
        self.phi_section = tk.Frame(c, bg=BG_DARK)
        self.phi_section.pack(fill=tk.X)

        self._mk_hdr(self.phi_section, 'PHI CUTS')
        phi_entry_row = tk.Frame(self.phi_section, bg=BG_DARK)
        phi_entry_row.pack(fill=tk.X, padx=12, pady=2)
        tk.Label(phi_entry_row, text='phi =', font=('Arial', 9),
                 fg=TEXT_SEC, bg=BG_DARK).pack(side=tk.LEFT)
        self.phi_entry = tk.Entry(phi_entry_row, width=7, font=('Courier', 9),
                                   fg=TEXT_PRI, bg=BG_INPUT,
                                   insertbackground=TEXT_PRI, bd=0)
        self.phi_entry.pack(side=tk.LEFT, padx=4)
        self.phi_entry.bind('<Return>', self._cb_add_phi_entry)
        tk.Label(phi_entry_row, text='deg', font=('Arial', 8),
                 fg=TEXT_SEC, bg=BG_DARK).pack(side=tk.LEFT)
        tk.Button(phi_entry_row, text='Add', font=('Arial', 9),
                  fg='white', bg=ACCENT, relief=tk.FLAT, bd=0,
                  command=self._cb_add_phi_entry).pack(side=tk.LEFT, padx=(6, 0))

        tk.Label(self.phi_section, text='Quick add:', font=('Arial', 8),
                 fg=TEXT_SEC, bg=BG_DARK, anchor='w').pack(
                 fill=tk.X, padx=12)
        phi_quick_row = tk.Frame(self.phi_section, bg=BG_DARK)
        phi_quick_row.pack(fill=tk.X, padx=12, pady=2)
        for av in [0, 30, 60, 90, 120, 150]:
            tk.Button(phi_quick_row, text=str(av), font=('Arial', 8),
                      fg=TEXT_PRI, bg=BG_PANEL, relief=tk.FLAT, bd=0, width=4,
                      command=lambda a=av: self._add_cut_direct(a)).pack(
                      side=tk.LEFT, padx=1)

        self._mk_btn(self.phi_section, '+ Add Default Set (0 to 150)',
                     self._cb_add_default_phi, BG_PANEL, TEXT_PRI)

        tk.Label(self.phi_section, text='Active phi cuts:',
                 font=('Arial', 8), fg=TEXT_SEC, bg=BG_DARK, anchor='w').pack(
                 fill=tk.X, padx=12, pady=(4, 0))

        self._phi_list_frame, self._phi_list_inner, self._phi_list_vsb = \
            self._mk_scrollable_list(self.phi_section)
        self._mk_btn(self.phi_section, 'X  Clear Phi Cuts',
                     self._cb_clear_phi, DANGER, 'white')

        # ── THETA CUTS section ────────────────────────────────────────────
        self.theta_section = tk.Frame(c, bg=BG_DARK)
        self.theta_section.pack(fill=tk.X)

        self._mk_hdr(self.theta_section, 'THETA CUTS')

        self.theta_range_label = tk.Label(
            self.theta_section,
            text='Grid range: load a file first',
            font=('Arial', 7), fg=ACCENT, bg=BG_DARK, anchor='w')
        self.theta_range_label.pack(fill=tk.X, padx=12, pady=(0, 2))

        theta_entry_row = tk.Frame(self.theta_section, bg=BG_DARK)
        theta_entry_row.pack(fill=tk.X, padx=12, pady=2)
        tk.Label(theta_entry_row, text='theta =', font=('Arial', 9),
                 fg=TEXT_SEC, bg=BG_DARK).pack(side=tk.LEFT)
        self.theta_entry = tk.Entry(theta_entry_row, width=7, font=('Courier', 9),
                                     fg=TEXT_PRI, bg=BG_INPUT,
                                     insertbackground=TEXT_PRI, bd=0)
        self.theta_entry.pack(side=tk.LEFT, padx=4)
        self.theta_entry.bind('<Return>', self._cb_add_theta_entry)
        tk.Label(theta_entry_row, text='deg', font=('Arial', 8),
                 fg=TEXT_SEC, bg=BG_DARK).pack(side=tk.LEFT)
        tk.Button(theta_entry_row, text='Add', font=('Arial', 9),
                  fg='white', bg=ACCENT, relief=tk.FLAT, bd=0,
                  command=self._cb_add_theta_entry).pack(side=tk.LEFT, padx=(6, 0))

        tk.Label(self.theta_section, text='Quick add:', font=('Arial', 8),
                 fg=TEXT_SEC, bg=BG_DARK, anchor='w').pack(
                 fill=tk.X, padx=12)

        # Dynamic theta quick-add bar — rebuilt on file load
        self.theta_quick_bar = tk.Frame(self.theta_section, bg=BG_DARK)
        self.theta_quick_bar.pack(fill=tk.X, padx=12, pady=2)

        self._mk_btn(self.theta_section, '+ Add Default Set',
                     self._cb_add_default_theta, BG_PANEL, TEXT_PRI)

        tk.Label(self.theta_section, text='Active theta cuts:',
                 font=('Arial', 8), fg=TEXT_SEC, bg=BG_DARK, anchor='w').pack(
                 fill=tk.X, padx=12, pady=(4, 0))

        self._theta_list_frame, self._theta_list_inner, self._theta_list_vsb = \
            self._mk_scrollable_list(self.theta_section)
        self._mk_btn(self.theta_section, 'X  Clear Theta Cuts',
                     self._cb_clear_theta, DANGER, 'white')

        # Footer export
        tk.Label(c, text='EXPORT', font=('Arial', 7, 'bold'),
                 fg=TEXT_SEC, bg=BG_DARK, anchor='w').pack(
                 fill=tk.X, padx=12, pady=(12, 0))
        self._mk_btn(c, 'Export PNG...', self._cb_export_dialog, BG_PANEL, TEXT_PRI)
        tk.Label(c, text='', bg=BG_DARK).pack(pady=6)

    def _on_sb_configure(self, _event=None):
        self._sb_canvas.configure(
            scrollregion=self._sb_canvas.bbox('all'))

    def _on_sb_canvas_configure(self, event):
        self._sb_canvas.itemconfig(self._sb_win, width=event.width)

    def _mk_hdr(self, parent, text):
        tk.Frame(parent, bg=DIVIDER, height=1).pack(fill=tk.X, pady=(6, 0))
        tk.Label(parent, text=text, font=('Arial', 7, 'bold'),
                 fg=TEXT_SEC, bg=BG_DARK, anchor='w').pack(
                 fill=tk.X, padx=12, pady=(2, 2))

    def _mk_btn(self, parent, text, cmd, bg, fg, pady=2):
        tk.Button(parent, text=text, font=('Arial', 8),
                  fg=fg, bg=bg, relief=tk.FLAT, bd=0,
                  command=cmd).pack(fill=tk.X, padx=12, pady=pady, ipady=5)

    def _mk_scrollable_list(self, parent):
        """Create a fixed-height scrollable cut list like MATLAB's clip/content/scroll."""
        outer = tk.Frame(parent, bg=BG_PANEL, height=CUT_LIST_H,
                         bd=1, relief=tk.SOLID)
        outer.pack(fill=tk.X, padx=12, pady=2)
        outer.pack_propagate(False)

        canvas = tk.Canvas(outer, bg=BG_PANEL, highlightthickness=0,
                           height=CUT_LIST_H)
        vsb = tk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=BG_PANEL)
        canvas.create_window((0, 0), window=inner, anchor='nw')

        inner.bind('<Configure>',
                   lambda e, c=canvas: c.configure(
                       scrollregion=c.bbox('all')))

        return canvas, inner, vsb

    # ── Plot area ──────────────────────────────────────────────────────────

    def _build_plot_area(self):
        pf = self.plot_frame

        # Tab bar
        tab_bar = tk.Frame(pf, bg='#E0E3E8', height=34)
        tab_bar.pack(fill=tk.X)
        tab_bar.pack_propagate(False)

        self._tab_ov_btn  = tk.Button(tab_bar, text=' Overlay Plot ',
                                       font=('Arial', 9), relief=tk.FLAT, bd=0,
                                       command=self._cb_tab_overlay)
        self._tab_ind_btn = tk.Button(tab_bar, text=' Individual Cuts ',
                                       font=('Arial', 9), relief=tk.FLAT, bd=0,
                                       command=self._cb_tab_individual)
        self._tab_ov_btn.pack(side=tk.LEFT, fill=tk.Y)
        self._tab_ind_btn.pack(side=tk.LEFT, fill=tk.Y)
        self._set_tab_highlight('overlay')

        # Overlay panel
        self.ov_panel  = tk.Frame(pf, bg='white')
        self.ov_panel.pack(fill=tk.BOTH, expand=True)

        self.ov_fig    = Figure(facecolor='white')
        self.ov_canvas = FigureCanvasTkAgg(self.ov_fig, master=self.ov_panel)
        self.ov_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._draw_empty_ax()

        # Individual panel (hidden initially)
        self.ind_panel = tk.Frame(pf, bg='white')

        # Sub-tab bar for "Both" mode
        self.ind_sub_bar   = tk.Frame(self.ind_panel, bg='#EEF0F4', height=30)
        self.ind_sub_bar.pack_propagate(False)
        self._ind_sub_phi_btn   = tk.Button(self.ind_sub_bar, text='Phi rows',
                                             font=('Arial', 9), relief=tk.FLAT, bd=0,
                                             command=lambda: self._cb_ind_sub_mode(1))
        self._ind_sub_theta_btn = tk.Button(self.ind_sub_bar, text='Theta rows',
                                             font=('Arial', 9), relief=tk.FLAT, bd=0,
                                             command=lambda: self._cb_ind_sub_mode(2))
        self._ind_sub_phi_btn.pack(side=tk.LEFT, fill=tk.Y, padx=4)
        self._ind_sub_theta_btn.pack(side=tk.LEFT, fill=tk.Y)

        # Scrollable individual rows
        self.ind_scroll_canvas = tk.Canvas(self.ind_panel, bg='white',
                                            highlightthickness=0)
        self.ind_vscroll = tk.Scrollbar(self.ind_panel, orient=tk.VERTICAL,
                                         command=self.ind_scroll_canvas.yview)
        self.ind_scroll_canvas.configure(yscrollcommand=self.ind_vscroll.set)
        self.ind_vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.ind_scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.ind_inner = tk.Frame(self.ind_scroll_canvas, bg='white')
        self.ind_canvas_win = self.ind_scroll_canvas.create_window(
            (0, 0), window=self.ind_inner, anchor='nw')

        self.ind_inner.bind('<Configure>', self._on_ind_configure)
        self.ind_scroll_canvas.bind('<Configure>', self._on_ind_canvas_configure)

    def _on_ind_configure(self, _e=None):
        self.ind_scroll_canvas.configure(
            scrollregion=self.ind_scroll_canvas.bbox('all'))

    def _on_ind_canvas_configure(self, event):
        self.ind_scroll_canvas.itemconfig(self.ind_canvas_win, width=event.width)

    def _set_tab_highlight(self, which):
        on_bg  = 'white';   on_fg  = '#1A1A1A'
        off_bg = '#DEE1E8'; off_fg = '#737373'
        if which == 'overlay':
            self._tab_ov_btn.config(bg=on_bg, fg=on_fg)
            self._tab_ind_btn.config(bg=off_bg, fg=off_fg)
        else:
            self._tab_ov_btn.config(bg=off_bg, fg=off_fg)
            self._tab_ind_btn.config(bg=on_bg, fg=on_fg)

    # ══════════════════════════════════════════════════════════════════════
    #  MODE / TAB CALLBACKS
    # ══════════════════════════════════════════════════════════════════════

    def _cb_set_mode(self, m):
        self.cut_mode = m
        self._apply_mode_visibility()
        self._redraw()

    def _apply_mode_visibility(self):
        on_c  = 'white';   on_t  = '#1A1A1A'
        off_c = '#DEE1E8'; off_t = '#737373'
        for btn in (self._mode_phi_btn, self._mode_theta_btn, self._mode_both_btn):
            btn.config(bg=off_c, fg=off_t)
        {1: self._mode_phi_btn,
         2: self._mode_theta_btn,
         3: self._mode_both_btn}[self.cut_mode].config(bg=on_c, fg=on_t)

        if self.cut_mode == 1:
            self.phi_section.pack(fill=tk.X)
            self.theta_section.pack_forget()
        elif self.cut_mode == 2:
            self.phi_section.pack_forget()
            self.theta_section.pack(fill=tk.X)
        else:
            self.phi_section.pack(fill=tk.X)
            self.theta_section.pack(fill=tk.X)

        # Sub-tab bar visibility
        if self.cut_mode == 3:
            self.ind_sub_bar.pack(fill=tk.X, before=self.ind_scroll_canvas)
            self._refresh_ind_sub_highlight()
        else:
            self.ind_sub_bar.pack_forget()

        self._on_sb_configure()

    def _refresh_ind_sub_highlight(self):
        on_c = 'white'; on_t = '#1A1A1A'; off_c = '#EEF0F4'; off_t = '#808080'
        self._ind_sub_phi_btn.config(bg=off_c, fg=off_t)
        self._ind_sub_theta_btn.config(bg=off_c, fg=off_t)
        if self.ind_sub_mode == 1:
            self._ind_sub_phi_btn.config(bg=on_c, fg=on_t)
        else:
            self._ind_sub_theta_btn.config(bg=on_c, fg=on_t)

    def _cb_ind_sub_mode(self, m):
        self.ind_sub_mode = m
        self._refresh_ind_sub_highlight()
        self._draw_individual()

    def _cb_tab_overlay(self):
        self.active_tab = 'overlay'
        self._set_tab_highlight('overlay')
        self.ind_panel.pack_forget()
        self.ov_panel.pack(fill=tk.BOTH, expand=True)
        self._draw_overlay()

    def _cb_tab_individual(self):
        self.active_tab = 'individual'
        self._set_tab_highlight('individual')
        self.ov_panel.pack_forget()
        self.ind_panel.pack(fill=tk.BOTH, expand=True)
        self._draw_individual()

    # ══════════════════════════════════════════════════════════════════════
    #  FILE LOAD
    # ══════════════════════════════════════════════════════════════════════

    def _cb_load(self, _event=None):
        path = filedialog.askopenfilename(
            title='Open GRASP .grd file',
            filetypes=[('GRD files', '*.grd'), ('All files', '*.*')])
        if not path:
            return
        try:
            self.all_freq_data, n_blocks = parse_grd_all(path)
        except Exception as exc:
            messagebox.showerror('Parse error', str(exc))
            return

        fname = path.split('/')[-1].split('\\')[-1]
        self.freq_values = [float('nan')] * n_blocks
        self.freq_labels = [f'Block {k+1}' for k in range(n_blocks)]
        self.current_freq = 0
        self.cuts = []
        self.theta_cuts = []

        self.freq_listbox.config(state=tk.NORMAL)
        self.freq_listbox.delete(0, tk.END)
        for lbl in self.freq_labels:
            self.freq_listbox.insert(tk.END, lbl)
        self.freq_listbox.selection_set(0)

        self.file_label.config(
            text=f'{fname}  ({n_blocks} blocks)', fg=ACCENT)

        # Detect real grid range from first block
        fd1 = self.all_freq_data[0]
        self.grid_phi_range_x = min(abs(fd1['theta_x'][0]), abs(fd1['theta_x'][-1]))
        self.grid_phi_range_y = min(abs(fd1['theta_y'][0]), abs(fd1['theta_y'][-1]))
        self.grid_range_max   = min(self.grid_phi_range_x, self.grid_phi_range_y)

        self.theta_range_label.config(
            text=f'Grid range: 0 to {self.grid_range_max:.1f} deg')

        self._rebuild_theta_quick_bar()
        self._rebuild_cut_list()
        self._rebuild_theta_cut_list()

        # Auto-populate sensible defaults
        self._cb_add_default_phi()
        self._cb_add_default_theta()
        self._redraw()

    # ══════════════════════════════════════════════════════════════════════
    #  THETA QUICK-ADD BAR
    # ══════════════════════════════════════════════════════════════════════

    def _rebuild_theta_quick_bar(self):
        for w in self.theta_quick_bar.winfo_children():
            w.destroy()
        if not np.isfinite(self.grid_range_max) or self.grid_range_max <= 0:
            return
        vals = self._nice_theta_vals(self.grid_range_max)
        for tv in vals:
            lbl = f'{tv:.4g}'
            tk.Button(self.theta_quick_bar, text=lbl, font=('Arial', 8),
                      fg=TEXT_PRI, bg=BG_PANEL, relief=tk.FLAT, bd=0, width=4,
                      command=lambda a=tv: self._add_theta_cut_direct(a)).pack(
                      side=tk.LEFT, padx=1)

    def _nice_theta_vals(self, r_max):
        step = r_max / 6
        nice = [0.5, 1, 2, 2.5, 5, 10, 15, 20, 30, 45]
        step = min(nice, key=lambda x: abs(x - step))
        vals = np.arange(step, r_max, step)
        vals = vals[vals < r_max]
        return vals[:6].tolist()

    # ══════════════════════════════════════════════════════════════════════
    #  FREQUENCY CALLBACKS
    # ══════════════════════════════════════════════════════════════════════

    def _cb_freq_select(self, _event=None):
        sel = self.freq_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self.all_freq_data):
            return
        self.current_freq = idx
        v = self.freq_values[idx]
        self.freq_entry.delete(0, tk.END)
        if not np.isnan(v):
            self.freq_entry.insert(0, f'{v:.4g}')
        self._redraw()

    def _cb_freq_label(self, _event=None):
        txt = self.freq_entry.get().strip()
        try:
            v = float(txt)
        except ValueError:
            messagebox.showwarning('Invalid', 'Enter a numeric frequency in GHz.')
            return
        idx = self.current_freq
        self.freq_values[idx] = v
        self.freq_labels[idx] = f'Block {idx+1}  {v:.4g} GHz'
        self.freq_listbox.delete(idx)
        self.freq_listbox.insert(idx, self.freq_labels[idx])
        self.freq_listbox.selection_set(idx)
        self._redraw()

    # ══════════════════════════════════════════════════════════════════════
    #  PHI CUT CONTROLS
    # ══════════════════════════════════════════════════════════════════════

    def _cb_add_phi_entry(self, _event=None):
        txt = self.phi_entry.get().strip().replace('deg', '')
        try:
            v = float(txt)
        except ValueError:
            messagebox.showwarning('Invalid', 'Enter a numeric angle.')
            return
        self._add_cut_direct(v)
        self.phi_entry.delete(0, tk.END)

    def _cb_add_default_phi(self, _event=None):
        for a in [0, 30, 60, 90, 120, 150]:
            self._add_cut_direct(a)

    def _cb_clear_phi(self):
        self.cuts = []
        self._rebuild_cut_list()
        self._redraw()

    def _add_cut_direct(self, a):
        if a in self.cuts:
            return
        self.cuts.append(a)
        self._rebuild_cut_list()
        self._redraw()

    def _remove_cut(self, a):
        if a in self.cuts:
            self.cuts.remove(a)
        self._rebuild_cut_list()
        self._redraw()

    # ══════════════════════════════════════════════════════════════════════
    #  THETA CUT CONTROLS
    # ══════════════════════════════════════════════════════════════════════

    def _cb_add_theta_entry(self, _event=None):
        txt = self.theta_entry.get().strip().replace('deg', '')
        try:
            v = float(txt)
        except ValueError:
            messagebox.showwarning('Invalid', 'Enter a numeric angle.')
            return
        if v < 0:
            messagebox.showwarning('Invalid',
                'Theta must be >= 0 (cone half-angle from boresight).')
            return
        if np.isfinite(self.grid_range_max) and v >= self.grid_range_max:
            messagebox.showwarning('Out of Grid Range',
                f'theta = {v:.4g} deg is outside the grid range '
                f'(0 to {self.grid_range_max:.1f} deg).\n'
                'This cut will have no data and will not be visible.')
            self.theta_entry.delete(0, tk.END)
            return
        self._add_theta_cut_direct(v)
        self.theta_entry.delete(0, tk.END)

    def _cb_add_default_theta(self, _event=None):
        if not np.isfinite(self.grid_range_max) or self.grid_range_max <= 0:
            for a in [5, 10, 15, 20, 30, 40]:
                self._add_theta_cut_direct(a)
            return
        for tv in self._nice_theta_vals(self.grid_range_max):
            self._add_theta_cut_direct(tv)

    def _cb_clear_theta(self):
        self.theta_cuts = []
        self._rebuild_theta_cut_list()
        self._redraw()

    def _add_theta_cut_direct(self, a):
        if a in self.theta_cuts:
            return
        self.theta_cuts.append(a)
        self._rebuild_theta_cut_list()
        self._redraw()

    def _remove_theta_cut(self, a):
        if a in self.theta_cuts:
            self.theta_cuts.remove(a)
        self._rebuild_theta_cut_list()
        self._redraw()

    # ══════════════════════════════════════════════════════════════════════
    #  CUT LIST REBUILDS
    # ══════════════════════════════════════════════════════════════════════

    def _rebuild_cut_list(self):
        self._rebuild_list_widget(
            self._phi_list_inner, self._phi_list_frame,
            self.cuts, 'phi', self._remove_cut)

    def _rebuild_theta_cut_list(self):
        self._rebuild_list_widget(
            self._theta_list_inner, self._theta_list_frame,
            self.theta_cuts, 'theta', self._remove_theta_cut)

    def _rebuild_list_widget(self, inner, canvas, angle_list, kind, remove_fn):
        for w in inner.winfo_children():
            w.destroy()

        if not angle_list:
            tk.Label(inner, text=f'No {kind} cuts added yet.',
                     font=('Arial', 8), fg=TEXT_SEC, bg=BG_PANEL).pack(
                     expand=True, pady=20)
            return

        for k, a in enumerate(angle_list):
            rgb = CUT_COLORS[k % len(CUT_COLORS)]
            row = tk.Frame(inner, bg=BG_PANEL)
            row.pack(fill=tk.X)

            tk.Frame(row, bg=rgb, width=4).pack(side=tk.LEFT, fill=tk.Y)
            lbl = f' {kind} = {a:.1f} deg'
            tk.Label(row, text=lbl, font=('Courier', 8),
                     fg=TEXT_PRI, bg=BG_PANEL, anchor='w').pack(
                     side=tk.LEFT, fill=tk.X, expand=True)
            tk.Button(row, text='x', font=('Arial', 8),
                      fg=TEXT_SEC, bg=BG_PANEL, relief=tk.FLAT, bd=0,
                      command=lambda av=a: remove_fn(av)).pack(side=tk.RIGHT)

    # ══════════════════════════════════════════════════════════════════════
    #  SCROLL WHEEL
    # ══════════════════════════════════════════════════════════════════════

    def _cb_scroll_wheel(self, event):
        # Determine scroll delta
        if event.num == 4:
            delta = -3
        elif event.num == 5:
            delta = 3
        else:
            delta = int(event.delta / 40) * -1

        if self.active_tab == 'individual':
            self.ind_scroll_canvas.yview_scroll(delta, 'units')
        else:
            self._sb_canvas.yview_scroll(delta, 'units')

    # ══════════════════════════════════════════════════════════════════════
    #  DRAWING
    # ══════════════════════════════════════════════════════════════════════

    def _redraw(self):
        if self.active_tab == 'overlay':
            self._draw_overlay()
        else:
            self._draw_individual()

    def _active_data(self):
        if not self.all_freq_data or self.current_freq >= len(self.all_freq_data):
            return None
        return self.all_freq_data[self.current_freq]

    def _freq_title_str(self):
        if not self.all_freq_data:
            return 'Radiation Pattern'
        v = self.freq_values[self.current_freq]
        if not np.isnan(v):
            return f'{v:.4g} GHz  (Block {self.current_freq+1})'
        elif len(self.all_freq_data) > 1:
            return f'Block {self.current_freq+1} / {len(self.all_freq_data)}'
        return 'Radiation Pattern'

    # ── Empty axes ─────────────────────────────────────────────────────────

    def _draw_empty_ax(self):
        self.ov_fig.clear()
        ax = self.ov_fig.add_subplot(111)
        self._style_ax(ax)
        ax.set_xlabel('Angle from boresight [deg]', fontsize=11)
        ax.set_ylabel('Amplitude [dB]', fontsize=11)
        ax.set_title('Radiation Pattern', fontsize=13, fontweight='bold')
        ax.text(0.5, 0.5, 'Open a .grd file to begin',
                transform=ax.transAxes,
                ha='center', va='center', fontsize=13,
                color='#B0B0B0', style='italic')
        self.ov_fig.tight_layout()
        self.ov_canvas.draw()

    # ── Overlay ────────────────────────────────────────────────────────────

    def _draw_overlay(self):
        fd = self._active_data()
        have = fd is not None and (self.cuts or self.theta_cuts)
        self.ov_fig.clear()

        if not have:
            self._draw_empty_ax()
            return

        r_max = grid_r_max(fd)
        t_str = self._freq_title_str()

        if self.cut_mode == 1:
            ax = self.ov_fig.add_subplot(111)
            self._plot_cut_set(ax, self.cuts, 'phi', fd, r_max,
                               (-r_max, r_max),
                               'Angle from boresight [deg]  (Phi Cut sweep)',
                               f'Phi Cuts  —  {t_str}')

        elif self.cut_mode == 2:
            ax = self.ov_fig.add_subplot(111)
            self._plot_cut_set(ax, self.theta_cuts, 'theta', fd, r_max,
                               (-180, 180),
                               'Angle from boresight [deg]  (Theta Cut sweep)',
                               f'Theta Cuts  —  {t_str}')

        else:  # both
            ax_l = self.ov_fig.add_subplot(121)
            ax_r = self.ov_fig.add_subplot(122)
            self._plot_cut_set(ax_l, self.cuts, 'phi', fd, r_max,
                               (-r_max, r_max),
                               'Angle from boresight [deg]  (Phi Cut sweep)',
                               'Phi Cuts')
            self._plot_cut_set(ax_r, self.theta_cuts, 'theta', fd, r_max,
                               (-180, 180),
                               'Angle from boresight [deg]  (Theta Cut sweep)',
                               'Theta Cuts')
            self.ov_fig.suptitle(t_str, fontsize=12, fontweight='bold')

        self.ov_fig.tight_layout()
        self.ov_canvas.draw()

    def _plot_cut_set(self, ax, angle_list, kind, fd, r_max, xlim, xlabel, title):
        self._style_ax(ax)
        ax.set_xlim(xlim)
        ax.set_ylim(-65, 2)
        ax.set_xlabel(xlabel, fontsize=10)
        ax.set_ylabel('Amplitude [dB]', fontsize=10)
        ax.set_title(title, fontsize=11, fontweight='bold')
        ax.axvline(0, color='#CCCCCC', linewidth=0.6, zorder=0)

        if not angle_list:
            ax.text(0.5, 0.5, f'No {kind} cuts added',
                    transform=ax.transAxes, ha='center', va='center',
                    fontsize=11, color='#B0B0B0', style='italic')
            return

        h_lines = []
        labels  = []

        for k, a in enumerate(angle_list):
            rgb = CUT_COLORS[k % len(CUT_COLORS)]
            rgb_dim = self._dim_color(rgb, 0.7)

            if kind == 'phi':
                r, eco, ecx = phi_cut(fd, a, N_POINTS, r_max)
                labels.append(f'phi={a:.1f} deg')
            else:
                r, eco, ecx = theta_cut(fd, a, N_POINTS)
                labels.append(f'theta={a:.1f} deg')

            ln, = ax.plot(r, eco, '-', color=rgb, linewidth=1.4)
            ax.plot(r, ecx, '--', color=rgb_dim, linewidth=0.9)
            h_lines.append(ln)

        # Legend phantom lines for co/cross
        h_co, = ax.plot([], [], '-',  color='#595959', linewidth=1.4)
        h_cx, = ax.plot([], [], '--', color='#8C8C8C', linewidth=0.9)

        lgd = ax.legend(
            h_lines + [h_co, h_cx],
            labels + ['Co-pol', 'Cross-pol'],
            loc='upper right', fontsize=7,
            frameon=True, edgecolor='#CCCCCC')
        lgd.set_title('cut / type')

    # ── Individual ─────────────────────────────────────────────────────────

    def _draw_individual(self):
        # Clear previous content
        for w in self.ind_inner.winfo_children():
            w.destroy()

        fd = self._active_data()

        if self.cut_mode == 1:
            cut_list = [(a, 'phi') for a in self.cuts]
        elif self.cut_mode == 2:
            cut_list = [(a, 'theta') for a in self.theta_cuts]
        else:
            if self.ind_sub_mode == 1:
                cut_list = [(a, 'phi') for a in self.cuts]
            else:
                cut_list = [(a, 'theta') for a in self.theta_cuts]

        if fd is None or not cut_list:
            return

        r_max = grid_r_max(fd)
        ROW_MIN_H = 220

        for k, (a, kind) in enumerate(cut_list):
            rgb = CUT_COLORS[k % len(CUT_COLORS)]
            rgb_dim = self._dim_color(rgb, 0.7)

            if kind == 'phi':
                r, eco, ecx = phi_cut(fd, a, N_POINTS, r_max)
                ttl   = f'Phi Cut:  phi = {a:.2f} deg'
                xlbl  = 'Angle from boresight [deg]'
                xlim  = (-r_max, r_max)
            else:
                r, eco, ecx = theta_cut(fd, a, N_POINTS)
                ttl   = f'Theta Cut:  theta = {a:.2f} deg'
                xlbl  = 'Angle from boresight [deg]'
                xlim  = (-180, 180)

            row_frame = tk.Frame(self.ind_inner, bg='white',
                                  height=ROW_MIN_H)
            row_frame.pack(fill=tk.X, expand=True)
            row_frame.pack_propagate(False)

            fig = Figure(facecolor='white', figsize=(6, 2.2))
            ax  = fig.add_subplot(111)
            self._style_ax(ax)
            ax.set_xlim(xlim)
            ax.set_ylim(-65, 2)
            ax.set_xlabel(xlbl, fontsize=9)
            ax.set_ylabel('Amplitude [dB]', fontsize=9)
            ax.set_title(ttl, fontsize=10, fontweight='bold', color=rgb)
            ax.axvline(0, color='#CCCCCC', linewidth=0.5, zorder=0)
            ax.plot(r, eco, '-',  color=rgb,     linewidth=1.5, label='Co-pol')
            ax.plot(r, ecx, '--', color=rgb_dim, linewidth=1.0, label='Cross-pol')
            ax.legend(fontsize=8, loc='upper right', frameon=True,
                      edgecolor='#CCCCCC')
            fig.tight_layout(pad=1.0)

            canv = FigureCanvasTkAgg(fig, master=row_frame)
            canv.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            canv.draw()

    # ── Style helpers ──────────────────────────────────────────────────────

    def _style_ax(self, ax):
        ax.set_facecolor(AXIS_BG)
        ax.tick_params(direction='out', colors='#737373')
        ax.spines['bottom'].set_color('#737373')
        ax.spines['top'].set_color('#737373')
        ax.spines['left'].set_color('#737373')
        ax.spines['right'].set_color('#737373')
        ax.grid(True, color=GRID_CLR, linewidth=0.8)

    def _dim_color(self, hex_color, t):
        """Blend hex_color toward white by factor t (0=white,1=original)."""
        c = plt.matplotlib.colors.to_rgb(hex_color)
        return tuple(v * t + 0.3 * (1 - t) for v in c)

    # ══════════════════════════════════════════════════════════════════════
    #  EXPORT PNG
    # ══════════════════════════════════════════════════════════════════════

    def _cb_export_dialog(self, _event=None):
        if not self.all_freq_data:
            messagebox.showwarning('Nothing to export', 'Load a .grd file first.')
            return

        fd = self._active_data()
        r_max = grid_r_max(fd)

        phi_list   = [(a, 'phi')   for a in self.cuts]
        theta_list = [(a, 'theta') for a in self.theta_cuts]
        all_cuts   = phi_list + theta_list

        # Build item list
        items = ['[Overlay] All cuts (current view)']
        for a, _ in phi_list:
            items.append(f'[Individual] Phi cut  phi={a:.1f} deg')
        for a, _ in theta_list:
            items.append(f'[Individual] Theta cut  theta={a:.1f} deg')
        items.append('--- Export ALL individual cuts as separate files ---')

        dlg = tk.Toplevel(self.root)
        dlg.title('Export PNG')
        dlg.geometry('440x320')
        dlg.resizable(False, False)
        dlg.configure(bg='#F5F6F8')
        dlg.grab_set()

        tk.Label(dlg, text='Select what to export:',
                 font=('Arial', 10, 'bold'), bg='#F5F6F8').pack(
                 anchor='w', padx=16, pady=(12, 4))

        lb = tk.Listbox(dlg, font=('Courier', 9), height=10,
                        selectbackground=ACCENT, selectforeground='white',
                        activestyle='none')
        lb.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)
        for item in items:
            lb.insert(tk.END, item)
        lb.selection_set(0)

        btn_row = tk.Frame(dlg, bg='#F5F6F8')
        btn_row.pack(fill=tk.X, padx=16, pady=8)

        def do_export():
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            sel_str = items[idx]

            if 'Export ALL individual cuts' in sel_str:
                if not all_cuts:
                    messagebox.showwarning('Empty', 'No individual cuts to export.')
                    return
                folder = filedialog.askdirectory(title='Choose folder')
                if not folder:
                    return
                for i, (a, kind) in enumerate(all_cuts):
                    self._export_single_cut(a, kind, fd, r_max, folder, i)
                dlg.destroy()
                messagebox.showinfo('Done',
                    f'Exported {len(all_cuts)} files to:\n{folder}')
                return

            if idx == 0:
                path = filedialog.asksaveasfilename(
                    defaultextension='.png',
                    filetypes=[('PNG', '*.png')],
                    initialfile='overlay.png')
                if not path:
                    return
                self._export_overlay(path, fd, r_max)
                dlg.destroy()
                messagebox.showinfo('Done', f'Saved: {path}')
                return

            cut_idx = idx - 1
            if cut_idx >= len(all_cuts):
                return
            a, kind = all_cuts[cut_idx]
            default_name = f'{kind}_cut_{a:.0f}deg.png'
            path = filedialog.asksaveasfilename(
                defaultextension='.png',
                filetypes=[('PNG', '*.png')],
                initialfile=default_name)
            if not path:
                return
            self._export_single_cut(a, kind, fd, r_max, None, None, out_path=path)
            dlg.destroy()
            messagebox.showinfo('Done', f'Saved: {path}')

        tk.Button(btn_row, text='Export Selected', font=('Arial', 9),
                  fg='white', bg=ACCENT, relief=tk.FLAT, bd=0,
                  command=do_export).pack(side=tk.LEFT, ipadx=8, ipady=4)
        tk.Button(btn_row, text='Cancel', font=('Arial', 9),
                  bg='#DEE1E8', relief=tk.FLAT, bd=0,
                  command=dlg.destroy).pack(side=tk.LEFT, padx=8, ipadx=8, ipady=4)

    def _export_overlay(self, out_path, fd, r_max):
        t_str = self._freq_title_str()
        fig = Figure(facecolor='white', figsize=(12, 7))

        if self.cut_mode == 1:
            ax = fig.add_subplot(111)
            self._plot_cut_set(ax, self.cuts, 'phi', fd, r_max,
                               (-r_max, r_max),
                               'Angle from boresight [deg]  (Phi Cut sweep)',
                               f'Phi Cuts  —  {t_str}')
        elif self.cut_mode == 2:
            ax = fig.add_subplot(111)
            self._plot_cut_set(ax, self.theta_cuts, 'theta', fd, r_max,
                               (-180, 180),
                               'Angle from boresight [deg]  (Theta Cut sweep)',
                               f'Theta Cuts  —  {t_str}')
        else:
            ax_l = fig.add_subplot(121)
            ax_r = fig.add_subplot(122)
            self._plot_cut_set(ax_l, self.cuts, 'phi', fd, r_max,
                               (-r_max, r_max),
                               'Angle from boresight [deg]  (Phi Cut sweep)',
                               'Phi Cuts')
            self._plot_cut_set(ax_r, self.theta_cuts, 'theta', fd, r_max,
                               (-180, 180),
                               'Angle from boresight [deg]  (Theta Cut sweep)',
                               'Theta Cuts')
            fig.suptitle(t_str, fontsize=13, fontweight='bold')

        fig.tight_layout()
        fig.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close('all')

    def _export_single_cut(self, a, kind, fd, r_max, folder, idx, out_path=None):
        if out_path is None:
            fname = f'{kind}_cut_{a:.0f}deg.png'
            out_path = f'{folder}/{fname}'

        rgb = CUT_COLORS[(idx or 0) % len(CUT_COLORS)]
        rgb_dim = self._dim_color(rgb, 0.7)

        fig = Figure(facecolor='white', figsize=(9, 5))
        ax  = fig.add_subplot(111)
        self._style_ax(ax)

        if kind == 'phi':
            r, eco, ecx = phi_cut(fd, a, N_POINTS, r_max)
            ttl  = f'Phi Cut:  phi = {a:.2f} deg'
            xlim = (-r_max, r_max)
        else:
            r, eco, ecx = theta_cut(fd, a, N_POINTS)
            ttl  = f'Theta Cut:  theta = {a:.2f} deg'
            xlim = (-180, 180)

        ax.plot(r, eco, '-',  color=rgb,     linewidth=1.8, label='Co-pol')
        ax.plot(r, ecx, '--', color=rgb_dim, linewidth=1.2, label='Cross-pol')
        ax.set_xlim(xlim)
        ax.set_ylim(-65, 2)
        ax.set_xlabel('Angle from boresight [deg]', fontsize=11)
        ax.set_ylabel('Amplitude [dB]', fontsize=11)
        ax.set_title(ttl, fontsize=12, fontweight='bold', color=rgb)
        ax.axvline(0, color='#CCCCCC', linewidth=0.6, zorder=0)
        ax.legend(fontsize=10, loc='upper right', frameon=True, edgecolor='#CCCCCC')
        fig.tight_layout()
        fig.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close('all')
