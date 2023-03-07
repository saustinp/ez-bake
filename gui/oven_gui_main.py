import os
import numpy as np
from pathlib import Path
import time
from datetime import datetime
from datetime import timedelta
from tkinter.filedialog import askopenfilename
from scipy import interpolate
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.scrolled import ScrolledText
import serial.tools.list_ports
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

class App(ttk.Window):
    def __init__(self, window_title=None, icon=None, hidpi_bool=False):

        if window_title and icon:

            super().__init__(title=window_title, iconphoto=icon)  # iconphoto has to be None in order to override with custom icon

            # icon help: https://stackoverflow.com/questions/11176638/tkinter-tclerror-error-reading-bitmap-file
            self.iconphoto(True, tk.PhotoImage(file=icon))

        elif window_title:
            super().__init__(title=window_title)

        elif icon:
            super().__init__(iconphoto=icon)  # iconphoto has to be None in order to override with custom icon

            self.iconphoto(True, tk.PhotoImage(file=icon))
        
        self.hidpi_bool = hidpi_bool

        if not self.hidpi_bool:
            def_font = tk.font.nametofont("TkDefaultFont")
            def_font.config(size=10)

        self.data_dirname = self.get_datetime_str()
        self.data_dirname = f'./runs/{self.data_dirname}'
        os.makedirs(self.data_dirname)

        ############### Initialize all variables ###############
        # Theme variable
        self.selected_theme = tk.StringVar(value='Light')
        self.selected_theme.trace("w", lambda *_:self.update_theme(self.selected_theme))

        # COM port variable
        self.controller_com_port_is_selected = None
        self.selected_controller_comport = tk.StringVar(value='None')
        self.selected_controller_comport.trace("w", lambda *_:self.update_com_port_controller())

        self.fan1_com_port_is_selected = None
        self.selected_fan1_comport = tk.StringVar(value='None')
        self.selected_fan1_comport.trace("w", lambda *_:self.update_com_port_fan1())

        self.fan2_com_port_is_selected= None
        self.selected_fan2_comport = tk.StringVar(value='None')
        self.selected_fan2_comport.trace("w", lambda *_:self.update_com_port_fan2())

        self.estop_bool = 0

        # Plot scaling variable
        self.plt_scale_var = tk.StringVar(value='1 minute')
        self.plt_scale_var.trace("w", lambda *_:self.draw_plot())

        # Autosequence variable
        self.auto_seq_fname = tk.StringVar(value='None')
        self.auto_seq_fname.trace("w", lambda *_:self.update_auto_seq_pane())

        self.loaded_csv_var = tk.StringVar()
        self.loaded_csv_bool = 0
        self.auto_sequence = None

        # Initializing serial port
        self.ser_controller = None
        self.ser_fan1 = None
        self.ser_fan2 = None

        # Lists to record the temperature and setpoint history
        self.history_time = []
        self.history_temp = []
        self.history_setpoint = []
        self.history_mode = []
        self.history_estop = []
        self.history_status = []
        self.history_fan1 = []
        self.history_fan2 = []

        self.fan1_rpm = 0
        self.fan2_rpm = 0

        self.timebase = None

        self.tc_readings = np.zeros(6)

        self.temp_mean = None
        self.temp_std = None
        self.setpoint = 0

        self.lbl_preheat = None
        self.prog_bar_preheating = None

        self.null_time = '00:00:00'
        self.str_rel_time = self.null_time

        self.seq_minimap = None

        self.btn_abort_seq_auto = None
        self.str_heater_status = None

        ###########################################

        self.root = ttk.Frame(self, padding=10)

        self.sty = ttk.Style()
        self.sty.theme_use('sandstone')

        # themes = ['sandstone', 'darkly']   # Names for light and dark themes
        self.themes = ['Dark', 'Light']

        if self.hidpi_bool:
            self.frm_title = ttk.Frame(self.root, padding=(10, 10, 10, 0))
        else:
            self.frm_title = ttk.Frame(self.root)
            
        self.frm_title.grid(row=0, column=0, columnspan=2, rowspan=1, sticky='ew')

        self.str_status = tk.StringVar(value='INACTIVE')
        self.status_colors = {'INACTIVE': 'black', 'CONNECTED': 'blue', 'RUNNING': 'green', 'ESTOPPED': 'red'}

        if self.hidpi_bool:
            self.lbl_title = ttk.Label(master=self.frm_title, text="Oven Control", font="-size 24 -weight bold")
            self.lbl_status = ttk.Label(master=self.frm_title, textvariable=self.str_status, font="-size 18 -weight bold", bootstyle=(SECONDARY))
            self.lbl_status_text = ttk.Label(master=self.frm_title, text="STATUS: ", font="-size 18 -weight bold")
        else:
            self.lbl_title = ttk.Label(master=self.frm_title, text="Oven Control", font="-size 18 -weight bold")
            self.lbl_status = ttk.Label(master=self.frm_title, textvariable=self.str_status, font="-size 14 -weight bold", bootstyle=(SECONDARY))
            self.lbl_status_text = ttk.Label(master=self.frm_title, text="STATUS: ", font="-size 14 -weight bold")

        self.lbl_title.pack(side=LEFT)
        self.lbl_status.pack(side=RIGHT)

        self.lbl_status_text.pack(side=RIGHT)

        self.separator2 = tk.Frame(self.root, bd=10, relief='sunken', height=4)
        self.separator2.grid(row=1, column=0, columnspan=2, rowspan=1, pady=10, padx=10, sticky='ew')
        
        # Main left and right container frames
        self.lframe = ttk.Frame(self.root)
        self.lframe.grid(row=2, column=0, padx=10, pady=10, sticky='nsew')

        self.rframe = ttk.Frame(self.root)
        self.rframe.grid(row=2, column=1, padx=10, pady=10, sticky='nsew')

        if self.hidpi_bool:
            self.root.columnconfigure(0, minsize=1400, weight=1)
            self.root.columnconfigure(1, minsize=900, weight=1)
            self.root.rowconfigure(2, minsize=1500, weight=1)
        else:
            self.root.columnconfigure(0, minsize=900, weight=1)
            self.root.columnconfigure(1, minsize=500, weight=1)
            self.root.rowconfigure(2, minsize=800, weight=1)

        self.frm_theme_selection = ttk.Labelframe(master=self.lframe, text="Settings", padding=10, bootstyle=INFO)
        self.frm_theme_selection.grid(row=0, column=0, sticky='ew', padx=10, pady=10)
        self.lframe.columnconfigure(0, minsize=self.lframe.winfo_width(), weight=1)

        # Select a Theme
        self.menu_theme = ttk.Menu(self.root)
        for t in self.themes:
            self.menu_theme.insert_radiobutton(label=t, value=t, variable=self.selected_theme, index=0)

        self.lbl_theme_select = ttk.Label(self.frm_theme_selection, text="Select a theme:", font='-size 12')
        self.lbl_theme_select.grid(row=0, column=0, padx=5, pady=5, sticky='e')

        self.mb_theme = ttk.Menubutton(
            master=self.frm_theme_selection,
            textvariable=self.selected_theme,
            bootstyle=(SECONDARY, OUTLINE),
            menu=self.menu_theme)
        self.mb_theme.grid(row=0, column=1, padx=5, pady=5, sticky='w')

        # Select a Controller COM Port
        self.lbl_controller_com_port = ttk.Label(self.frm_theme_selection, text="Controller COM Port:", anchor='e', font='-size 12')
        self.lbl_controller_com_port.grid(row=0, column=2, padx=10, pady=10, sticky='e')

        self.ports = serial.tools.list_ports.comports()
        self.dev = [port.device for port in self.ports]

        self.menu_controller_com = ttk.Menu(self.root)
        for dev in self.dev:
            self.menu_controller_com.insert_radiobutton(label=dev, value=dev, variable=self.selected_controller_comport, index=0)

        self.mb_controller_com = ttk.Menubutton(
            master=self.frm_theme_selection,
            textvariable=self.selected_controller_comport,
            bootstyle=(SECONDARY, OUTLINE),
            menu=self.menu_controller_com)
        self.mb_controller_com.grid(row=0, column=3, padx=5, pady=5, sticky='w')

        # Select a COM Port for Fan 1
        self.lbl_fan1_com_port = ttk.Label(self.frm_theme_selection, text="Fan 1 COM Port:", anchor='e', font='-size 12')
        self.lbl_fan1_com_port.grid(row=0, column=4, padx=10, pady=10, sticky='e')

        self.menu_fan1_com = ttk.Menu(self.root)
        for dev in self.dev:
            self.menu_fan1_com.insert_radiobutton(label=dev, value=dev, variable=self.selected_fan1_comport, index=0)

        self.mb_fan1_com = ttk.Menubutton(
            master=self.frm_theme_selection,
            textvariable=self.selected_fan1_comport,
            bootstyle=(SECONDARY, OUTLINE),
            menu=self.menu_fan1_com)
        self.mb_fan1_com.grid(row=0, column=5, padx=5, pady=5, sticky='w')

        # Select a COM Port for Fan 2
        self.lbl_fan2_com_port = ttk.Label(self.frm_theme_selection, text="Fan 2 COM Port:", anchor='e', font='-size 12')
        self.lbl_fan2_com_port.grid(row=0, column=6, padx=10, pady=10, sticky='e')

        self.menu_fan2_com = ttk.Menu(self.root)
        for dev in self.dev:
            self.menu_fan2_com.insert_radiobutton(label=dev, value=dev, variable=self.selected_fan2_comport, index=0)

        self.mb_fan2_com = ttk.Menubutton(
            master=self.frm_theme_selection,
            textvariable=self.selected_fan2_comport,
            bootstyle=(SECONDARY, OUTLINE),
            menu=self.menu_fan2_com)
        self.mb_fan2_com.grid(row=0, column=7, padx=5, pady=5, sticky='w')

        self.btn_estop = ttk.Button(master=self.frm_theme_selection, width=15, text="ESTOP", bootstyle=DANGER, command=lambda:self.on_estop())
        self.btn_estop.grid(row=0, column=8, padx=10, pady=10, ipady=15)

        self.frm_theme_selection.columnconfigure(0, weight=1)
        self.frm_theme_selection.columnconfigure(1, weight=1)
        self.frm_theme_selection.columnconfigure(2, weight=1)
        self.frm_theme_selection.columnconfigure(3, weight=1)
        self.frm_theme_selection.columnconfigure(4, weight=1)
        self.frm_theme_selection.columnconfigure(5, weight=1)
        self.frm_theme_selection.columnconfigure(6, weight=1)
        self.frm_theme_selection.columnconfigure(7, weight=1)
        self.frm_theme_selection.columnconfigure(8, weight=1)

        # Main temperature plot
        self.fig_main_temp_plot = Figure()
        self.ax = self.fig_main_temp_plot.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.fig_main_temp_plot, master=self.lframe)
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky='nsew')

        self.draw_plot()
        self.lframe.rowconfigure(1, weight=1)

        self.frm_plot_options = ttk.Frame(master=self.lframe, padding=10)
        self.frm_plot_options.grid(row=2, column=0, sticky='ew')

        self.btn_savefig = ttk.Button(master=self.frm_plot_options, text='Save Plot...', width=15, bootstyle=(INFO, OUTLINE), command=lambda:self.savefig())
        self.btn_savefig.pack(side=RIGHT, padx=150, pady=5)

        self.btn_savedata = ttk.Button(master=self.frm_plot_options, text='Save Data...', width=15, bootstyle=(INFO, OUTLINE), command=lambda:self.save_data_to_csv())
        self.btn_savedata.pack(side=RIGHT, padx=150, pady=5)

        self.time_scales = ['1 minute', '3 minutes', '5 minutes', '10 minutes', '20 minutes', '40 minutes', '60 minutes', '120 minutes', "All time"][::-1]
        self.menu_scale = ttk.Menu(self.root)
        for scale in self.time_scales:
            self.menu_scale.insert_radiobutton(label=scale, value=scale, index=0, variable=self.plt_scale_var)

        self.mb = ttk.Menubutton(
            width=10,
            master=self.frm_plot_options,
            textvariable=self.plt_scale_var,
            bootstyle=(SECONDARY, OUTLINE),
            menu=self.menu_scale)
        self.mb.pack(side=RIGHT, padx=10, pady=5)

        self.lbl_time_range = ttk.Label(self.frm_plot_options, text="Time Range:", anchor='e')
        self.lbl_time_range.pack(side=RIGHT, anchor=N, padx=10, pady=5)

        # Log frame
        self.frm_log = ttk.Labelframe(master=self.lframe, text="Log", padding=10, bootstyle=INFO)
        self.frm_log.grid(row=3, column=0, sticky='ew')

        # Log
        self.log = ScrolledText(master=self.lframe, height=5, width=50, autohide=True)
        self.log.grid(row=3, column=0, sticky='nsew')
        self.write_log('Initialized. Select a COM port to connect...')

        # Status Frame
        self.frm_status = ttk.Labelframe(master=self.rframe, text="System Status", padding=10, bootstyle=INFO)
        self.frm_status.grid(row=0, column=0, sticky='ew', padx=10, pady=10)
        self.rframe.columnconfigure(0, minsize=self.rframe.winfo_width(), weight=1)

        if self.hidpi_bool:
            self.status_fsize = 12
        else:
            self.status_fsize = 8

        # Status frame labels
        self.str_heater_status = tk.StringVar(value='HEATER OFF')
        self.lbl_mean_temp = ttk.Label(master=self.frm_status, text='Average Temperature: ', font=f"-size {self.status_fsize}")
        self.lbl_stddev = ttk.Label(master=self.frm_status, text= f'1-\N{GREEK SMALL LETTER SIGMA} Std. Deviation: ', font=f"-size {self.status_fsize}")
        self.lbl_setpoint = ttk.Label(master=self.frm_status, text= 'Setpoint: ', font=f"-size {self.status_fsize}")
        self.lbl_action = ttk.Label(master=self.frm_status, text= 'Action: ', font=f"-size {self.status_fsize}")
        self.lbl_mode = ttk.Label(master=self.frm_status, text= 'Mode: ', font=f"-size {self.status_fsize}")
        self.lbl_heater_status = ttk.Label(master=self.frm_status, textvariable=self.str_heater_status, font=f"-size {self.status_fsize}")

        self.lbl_mean_temp.grid(row=0, column=0, sticky='w')
        self.lbl_stddev.grid(row=2, column=0, sticky='w')
        self.lbl_setpoint.grid(row=1, column=0, sticky='w')
        self.lbl_action.grid(row=4, column=0, sticky='w')
        self.lbl_mode.grid(row=3, column=0, sticky='w')
        self.lbl_heater_status.grid(row=5, column=2)

        self.flt_mean_temp = tk.DoubleVar(value=f'-- \N{DEGREE CELSIUS}')
        self.flt_stddev = tk.DoubleVar(value=f'-- \N{DEGREE CELSIUS}')
        self.flt_setpoint = tk.DoubleVar(value=f'-- \N{DEGREE CELSIUS}')
        self.str_action = tk.StringVar(value='OFF')
        self.str_mode = tk.StringVar(value='NOT SET')

        self.lbl_mean_temp_val = ttk.Label(master=self.frm_status, textvariable=self.flt_mean_temp, font=f"-size {self.status_fsize}")
        self.lbl_stddev_val = ttk.Label(master=self.frm_status, textvariable=self.flt_stddev, font=f"-size {self.status_fsize}")
        self.lbl_setpoint_val = ttk.Label(master=self.frm_status, textvariable=self.flt_setpoint, font=f"-size {self.status_fsize}")
        self.lbl_action_val = ttk.Label(master=self.frm_status, textvariable=self.str_action, font=f"-size {self.status_fsize}")
        self.lbl_mode_val = ttk.Label(master=self.frm_status, textvariable=self.str_mode, font=f"-size {self.status_fsize}")

        self.lbl_mean_temp_val.grid(row=0, column=1, sticky='w')
        self.lbl_stddev_val.grid(row=2, column=1, sticky='w')
        self.lbl_setpoint_val.grid(row=1, column=1, sticky='w')
        self.lbl_action_val.grid(row=4, column=1, sticky='w')
        self.lbl_mode_val.grid(row=3, column=1, sticky='w')

        if self.hidpi_bool:
            self.heater_canvas = tk.Canvas(self.frm_status, width=200, height=200)
            self.heater_canvas.grid(row=0, column=2, rowspan=5)
            self.status_indicator = self.heater_canvas.create_oval(0, 0, 180, 180, fill='gray')
        else:
            self.heater_canvas = tk.Canvas(self.frm_status, width=100, height=100)
            self.heater_canvas.grid(row=0, column=2, rowspan=5)
            self.status_indicator = self.heater_canvas.create_oval(10, 0, 90, 80, fill='gray')

        self.frm_status.columnconfigure(0, weight=1)
        self.frm_status.columnconfigure(1, weight=1)
        self.frm_status.columnconfigure(2, weight=1)

        self.frm_status.rowconfigure(0, weight=1)
        self.frm_status.rowconfigure(1, weight=1)
        self.frm_status.rowconfigure(2, weight=1)
        self.frm_status.rowconfigure(3, weight=1)
        self.frm_status.rowconfigure(4, weight=1)
        self.frm_status.rowconfigure(5, weight=1)

        # Control pane - manual or autosequence selector
        self.frm_control = ttk.Labelframe(master=self.rframe, text="Control", padding=10, bootstyle=INFO)
        if self.hidpi_bool:
            self.frm_control.grid(row=1, column=0, sticky='ew', padx=10, pady=10)
        else:
            self.frm_control.grid(row=1, column=0, sticky='ew', padx=10)

        if self.hidpi_bool:
            self.nb = ttk.Notebook(self.frm_control, padding=5)
        else:    
            self.nb = ttk.Notebook(self.frm_control, padding=10)

        self.nb.grid(row=0, column=0, sticky='nsew')
        self.frm_manual = ttk.Frame(self.nb)
        self.frm_auto = ttk.Frame(self.nb)
        self.nb.add(self.frm_manual, text="Manual")
        self.nb.add(self.frm_auto, text="Automatic")

        # Manual mode
        self.lbl_manual_msg = ttk.Label(master=self.frm_manual, text='Enter a manual setpoint < 140 \N{DEGREE CELSIUS}:')
        self.lbl_manual_msg.grid(row=0, column=0, sticky='s', padx=10, pady=50)

        self.entry_manual_setpoint = ttk.Entry(self.frm_manual)
        self.entry_manual_setpoint.grid(row=1, column=0, sticky='nsew')

        self.btn_submit_manual = ttk.Button(master=self.frm_manual, width=10, text="START", bootstyle=SUCCESS, command=lambda:self.on_set_manual_setpoint())
        self.btn_submit_manual.grid(row=2, column=0, padx=10, pady=10)

        # Auto mode
        self.btn_select_seq_auto = ttk.Button(master=self.frm_auto, width=15, text="Select Sequence...", bootstyle=INFO, command=self.on_open_sequence)
        self.btn_select_seq_auto.grid(row=1, column=0, padx=10, pady=10)

        self.btn_submit_seq_auto = ttk.Button(master=self.frm_auto, width=10, text="START", bootstyle=SUCCESS, state=DISABLED, command=self.on_start_auto_sequence)
        self.btn_submit_seq_auto.grid(row=1, column=1, padx=10, pady=10)

        # Initialize auto tab with a message telling the user to input a sequence
        self.lbl_init_auto = ttk.Label(master=self.frm_auto, text='Please select a temperature profile to run.')
        self.lbl_init_auto.grid(row=0, column=0, columnspan=2, sticky='w', padx=10, pady=100)

        self.rframe.rowconfigure(1, weight=1)

        # Monitor Frame
        # Padding depends on screen resolution
        if self.hidpi_bool:
            self.frm_monitor = ttk.Labelframe(master=self.rframe, text="Monitor", padding=10, bootstyle=INFO)
            self.frm_monitor.grid(row=2, column=0, sticky='ew', padx=10, pady=10)

            self.frm_temp_monitor = ttk.Frame(self.frm_monitor, padding=(20, 10, 10, 10))
            self.frm_temp_monitor.grid(row=0, column=0, sticky='ns')
            
            self.frm_fan_monitor = ttk.Frame(self.frm_monitor, padding=(60, 10, 10, 10))
            self.frm_fan_monitor.grid(row=0, column=1, sticky='ns')
        else:
            self.frm_monitor = ttk.Labelframe(master=self.rframe, text="Monitor", padding=10, bootstyle=INFO)
            self.frm_monitor.grid(row=2, column=0, sticky='ew', padx=10)

            self.frm_temp_monitor = ttk.Frame(self.frm_monitor, padding=(10, 0, 10, 0))
            self.frm_temp_monitor.grid(row=0, column=0, sticky='ns')
            
            self.frm_fan_monitor = ttk.Frame(self.frm_monitor, padding=(30, 0, 10, 0))
            self.frm_fan_monitor.grid(row=0, column=1, sticky='ns')

        # Temperature monitor labels
        self.str_tc1 = tk.StringVar(value=f'-- \N{DEGREE CELSIUS}')
        self.str_tc2 = tk.StringVar(value=f'-- \N{DEGREE CELSIUS}')
        self.str_tc3 = tk.StringVar(value=f'-- \N{DEGREE CELSIUS}')
        self.str_tc4 = tk.StringVar(value=f'-- \N{DEGREE CELSIUS}')
        self.str_tc5 = tk.StringVar(value=f'-- \N{DEGREE CELSIUS}')
        self.str_tc6 = tk.StringVar(value=f'-- \N{DEGREE CELSIUS}')
        self.tc_strs = [self.str_tc1, self.str_tc2, self.str_tc3, self.str_tc4, self.str_tc5, self.str_tc6]

        self.lbl_tc1 = ttk.Label(master=self.frm_temp_monitor, text='TC1: ', font=f"-size {self.status_fsize}")
        self.lbl_tc2 = ttk.Label(master=self.frm_temp_monitor, text='TC2: ', font=f"-size {self.status_fsize}")
        self.lbl_tc3 = ttk.Label(master=self.frm_temp_monitor, text='TC3: ', font=f"-size {self.status_fsize}")
        self.lbl_tc4 = ttk.Label(master=self.frm_temp_monitor, text='TC4: ', font=f"-size {self.status_fsize}")
        self.lbl_tc5 = ttk.Label(master=self.frm_temp_monitor, text='TC5: ', font=f"-size {self.status_fsize}")
        self.lbl_tc6 = ttk.Label(master=self.frm_temp_monitor, text='TC6: ', font=f"-size {self.status_fsize}")

        self.lbl_tc1.grid(row=0, column=0, sticky='w')
        self.lbl_tc2.grid(row=1, column=0, sticky='w')
        self.lbl_tc3.grid(row=2, column=0, sticky='w')
        self.lbl_tc4.grid(row=3, column=0, sticky='w')
        self.lbl_tc5.grid(row=4, column=0, sticky='w')
        self.lbl_tc6.grid(row=5, column=0, sticky='w')

        self.lbl_tc1_val = ttk.Label(master=self.frm_temp_monitor, textvariable=self.str_tc1, font=f"-size {self.status_fsize}")
        self.lbl_tc2_val = ttk.Label(master=self.frm_temp_monitor, textvariable=self.str_tc2, font=f"-size {self.status_fsize}")
        self.lbl_tc3_val = ttk.Label(master=self.frm_temp_monitor, textvariable=self.str_tc3, font=f"-size {self.status_fsize}")
        self.lbl_tc4_val = ttk.Label(master=self.frm_temp_monitor, textvariable=self.str_tc4, font=f"-size {self.status_fsize}")
        self.lbl_tc5_val = ttk.Label(master=self.frm_temp_monitor, textvariable=self.str_tc5, font=f"-size {self.status_fsize}")
        self.lbl_tc6_val = ttk.Label(master=self.frm_temp_monitor, textvariable=self.str_tc6, font=f"-size {self.status_fsize}")

        self.lbl_tc1_val.grid(row=0, column=1, sticky='w')
        self.lbl_tc2_val.grid(row=1, column=1, sticky='w')
        self.lbl_tc3_val.grid(row=2, column=1, sticky='w')
        self.lbl_tc4_val.grid(row=3, column=1, sticky='w')
        self.lbl_tc5_val.grid(row=4, column=1, sticky='w')
        self.lbl_tc6_val.grid(row=5, column=1, sticky='w')

        self.frm_status.columnconfigure(0, weight=1)
        self.frm_status.columnconfigure(1, weight=1)
        self.frm_status.columnconfigure(2, weight=1)

        self.frm_status.rowconfigure(0, weight=1)
        self.frm_status.rowconfigure(1, weight=1)
        self.frm_status.rowconfigure(2, weight=1)
        self.frm_status.rowconfigure(3, weight=1)
        self.frm_status.rowconfigure(4, weight=1)
        self.frm_status.rowconfigure(5, weight=1)


        # Fan status monitor labels
        self.str_fan1 = tk.StringVar(value=f'-- RPM')
        self.str_fan2 = tk.StringVar(value=f'-- RPM')

        self.lbl_fan1 = ttk.Label(master=self.frm_fan_monitor, text='Fan 1: ', font=f"-size {self.status_fsize}")
        self.lbl_fan2 = ttk.Label(master=self.frm_fan_monitor, text='Fan 2: ', font=f"-size {self.status_fsize}")

        self.lbl_fan1.grid(row=0, column=0, sticky='w')
        self.lbl_fan2.grid(row=1, column=0, sticky='w')

        self.lbl_fan1_val = ttk.Label(master=self.frm_fan_monitor, textvariable=self.str_fan1, font=f"-size {self.status_fsize}")
        self.lbl_fan2_val = ttk.Label(master=self.frm_fan_monitor, textvariable=self.str_fan2, font=f"-size {self.status_fsize}")

        self.lbl_fan1_val.grid(row=0, column=1, sticky='w')
        self.lbl_fan2_val.grid(row=1, column=1, sticky='w')

        self.frm_status.columnconfigure(0, weight=1)
        self.frm_status.columnconfigure(1, weight=1)
        self.frm_status.columnconfigure(2, weight=1)

        self.frm_status.rowconfigure(0, weight=1)
        self.frm_status.rowconfigure(1, weight=1)

        self.root.pack(fill=BOTH, expand=YES)


    def update_theme(self, sel_theme):
        theme = sel_theme.get()
        if theme == 'Light':
            theme_upd = 'sandstone'
        elif theme == 'Dark':
            theme_upd = 'darkly'
        self.sty.theme_use(theme_upd)

    def update_com_port_controller(self):
        """
        A temperature of 0 is written anytime a new COM port is selected
        """

        if self.controller_com_port_is_selected is None:
            self.controller_com_port_is_selected = self.selected_controller_comport.get()
            self.ser_controller = serial.Serial(self.controller_com_port_is_selected, 9600, timeout=1)
            self.ser_controller.write(b'0')
            self.reset_timebase()

            self.write_log(f'Connected to {self.controller_com_port_is_selected}')
            self.str_status.set('CONNECTED')
            self.lbl_status.config(foreground=self.status_colors['CONNECTED'])
            self.draw_plot()

        elif (self.controller_com_port_is_selected != self.selected_controller_comport.get() and self.selected_controller_comport.get() != 'None'):    # is not None prevents it from displaying the message when a port is disconnected
            change_com_port_bool = Messagebox.show_warning('You are already connected to a COM Port.\nConnecting to this COM Port will reset the current session and erase all history!')
            if change_com_port_bool:
                self.controller_com_port_is_selected = self.selected_controller_comport.get()
                self.ser_controller = serial.Serial(self.controller_com_port_is_selected, 9600, timeout=1)
                self.ser_controller.write(b'0')
                self.reset_timebase()

                self.write_log(f'Connected to {self.controller_com_port_is_selected}')
                self.str_status.set('CONNECTED')
                self.lbl_status.config(foreground=self.status_colors['CONNECTED'])
                self.draw_plot()

    def update_com_port_fan1(self):
        if self.fan1_com_port_is_selected is None:
            self.fan1_com_port_is_selected = self.selected_fan1_comport.get()
            self.ser_fan1 = serial.Serial(self.fan1_com_port_is_selected, 9600, timeout=1)
            self.write_log(f'Connected to {self.fan1_com_port_is_selected}')

        elif (self.fan1_com_port_is_selected != self.selected_fan1_comport.get() and self.selected_fan1_comport.get() != 'None'):    # is not None prevents it from displaying the message when a port is disconnected
            change_com_port_bool = Messagebox.show_warning('You are already connected to a COM Port!')
            if change_com_port_bool:
                self.fan1_com_port_is_selected = self.selected_fan1_comport.get()
                self.ser_fan1 = serial.Serial(self.fan1_com_port_is_selected, 9600, timeout=1)
                self.write_log(f'Connected to {self.fan1_com_port_is_selected}')

    def update_com_port_fan2(self):
        if self.fan2_com_port_is_selected is None:
            self.fan2_com_port_is_selected = self.selected_fan2_comport.get()
            self.ser_fan2 = serial.Serial(self.fan2_com_port_is_selected, 9600, timeout=1)
            self.write_log(f'Connected to {self.fan2_com_port_is_selected}')

        elif (self.fan2_com_port_is_selected != self.selected_fan2_comport.get() and self.selected_fan2_comport.get() != 'None'):    # is not None prevents it from displaying the message when a port is disconnected
            change_com_port_bool = Messagebox.show_warning('You are already connected to a COM Port!')
            if change_com_port_bool:
                self.fan2_com_port_is_selected = self.selected_fan2_comport.get()
                self.ser_fan2 = serial.Serial(self.fan2_com_port_is_selected, 9600, timeout=1)
                self.write_log(f'Connected to {self.fan2_com_port_is_selected}')

    def on_estop(self):
        if self.controller_com_port_is_selected is None:
            return
        else:
            self.estop_bool = 1
            self.set_setpoint(0)
            self.send_temp(self.ser_controller, 9000)
            self.btn_estop.config(state=DISABLED)
            self.str_status.set('ESTOPPED')
            self.lbl_status.config(foreground=self.status_colors['ESTOPPED'])
            self.write_log('---------- ESTOPPED ----------')

            # Stop any currently running sequence
            if 'AUTO' in self.str_mode.get():
                self.on_abort_auto_seq()
            elif 'MANUAL' in self.str_mode.get():
                self.str_mode.set('OFF')

    def get_mins_lims_from_plt_str(self):
        time_range = self.plt_scale_var.get().split(' ')[0]
        if 'all' in time_range.lower():
            if len(self.history_temp):
                time_range = self.history_time[-1]
            else:
                time_range = 1     # Default to 1 minute
        else:
            time_range = int(time_range)

        if len(self.history_temp):
            if self.history_time[-1] < time_range:
                xlim = [0, time_range]
            else:
                xlim = [self.history_time[-1]-time_range, self.history_time[-1]]

            # Get y range inside of time slice
            min_time_idx = np.argmin(np.abs(np.array(self.history_time)-np.array(xlim[0])))

            # Easier to work with numpy array than it is with a list of lists
            y_val_arry = np.column_stack((np.array(self.history_temp), self.history_setpoint))
            y_val_arry = y_val_arry[min_time_idx:]      # Clip the y values
            ylim = [y_val_arry.min()*0.8, y_val_arry.max()*1.1]

            time_val_arry = np.array(self.history_time)[min_time_idx:]      # Clip the time values
            setpoint_arry = np.array(self.history_setpoint)[min_time_idx:]      # Clip the setpoint

        else:       # No data values have been loaded into the arrays yet
            xlim = [0, time_range]
            ylim = [0, 100]
            time_val_arry = None
            y_val_arry = None
            setpoint_arry = None

        return xlim, ylim, time_val_arry, y_val_arry, setpoint_arry

    def on_open_sequence(self):
        fpath = askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if fpath:
            self.auto_seq_fname.set(str(fpath))

    def update_auto_seq_pane(self):
        fpath = self.auto_seq_fname.get()
        if fpath == 'None':     # No sequence loaded
            return
        else:
            if self.loaded_csv_bool:
                self.tv_autoseq.destroy()
                self.lbl_init_auto.destroy()
                self.canvas_autoseq.destroy()

            self.seq_fname = Path(fpath).name
            self.auto_sequence = np.loadtxt(fpath, delimiter=',', skiprows=1)

            self.lbl_init_auto.destroy()

            self.tv_autoseq = ttk.Treeview(master=self.frm_auto, columns=[0, 1], show=HEADINGS, height=5, selectmode='none')
            for row in self.auto_sequence:
                self.tv_autoseq.insert("", END, values=(row[0], row[1]))

            self.tv_autoseq.heading(0, text="Time (min)")
            self.tv_autoseq.heading(1, text="Temp (\N{DEGREE CELSIUS})")
            self.tv_autoseq.column(0, width=150)
            self.tv_autoseq.column(1, width=150, anchor=CENTER)
            self.tv_autoseq.grid(row=0, column=0, columnspan=2, sticky='ew', padx=15, pady=10)
            
            # Put the filepath in the "sequence loaded! label"
            self.loaded_csv_var.set(f'Sequence loaded! {self.seq_fname}')
            self.lbl_init_auto = ttk.Label(master=self.frm_auto, textvariable=self.loaded_csv_var, bootstyle=(SUCCESS))
            self.lbl_init_auto.grid(row=2, column=0, columnspan=2, sticky='ew', padx=15, pady=5)

            self.btn_submit_seq_auto.config(state=NORMAL)

            # Matplotlib plot sequence widget
            if self.hidpi_bool:
                self.fig_seq = Figure(figsize=(1, 3.5), dpi=100)
            else:
                self.fig_seq = Figure(figsize=(1, 2.1), dpi=100)
                
            self.seq_minimap = self.fig_seq.add_subplot(111)
            self.seq_minimap.plot(self.auto_sequence[:,0], self.auto_sequence[:,1], 'black')

            if self.hidpi_bool:
                self.seq_minimap.set_xlabel('Time [min]', fontsize=10)
                self.seq_minimap.set_ylabel(f'Temperature [\N{DEGREE CELSIUS}]', fontsize=10)
                self.seq_minimap.tick_params(axis='both', which='major', labelsize=10)
                self.seq_minimap.set_title('Sequence', fontsize=15)
            else:
                self.seq_minimap.set_xlabel('Time [min]', fontsize=5)
                self.seq_minimap.set_ylabel(f'Temperature [\N{DEGREE CELSIUS}]', fontsize=5)
                self.seq_minimap.tick_params(axis='both', which='major', labelsize=5)
                self.seq_minimap.set_title('Sequence', fontsize=6)

            self.canvas_autoseq = FigureCanvasTkAgg(self.fig_seq, master=self.frm_auto)
            if self.hidpi_bool:
                self.canvas_autoseq.get_tk_widget().grid(row=3, column=0, columnspan=2, sticky='nsew', pady=20, ipady=20)
            else:
                self.canvas_autoseq.get_tk_widget().grid(row=3, column=0, columnspan=2, sticky='nsew', pady=20, ipady=20)
                
            self.rframe.rowconfigure(1, weight=1)

            # Build an interpolation function for the autosequence
            self.auto_sequence_interp = interpolate.interp1d(self.auto_sequence[:,0], self.auto_sequence[:,1])

    def write_log(self, msg):
        self.log.insert(END, f'{self.get_datetime_log()} - {msg}\n')

    def draw_plot(self):

        xlim, ylim, time_arry, temp_as_arry, setpoint_arry = self.get_mins_lims_from_plt_str()

        self.fig_main_temp_plot.clear()
        self.ax = self.fig_main_temp_plot.add_subplot(111)

        if self.controller_com_port_is_selected:
            if time_arry is not None:
                for i in np.arange(self.history_temp[0].shape[0]):
                    self.ax.plot(time_arry, temp_as_arry[:,i], label=f'TC {i+1}')

                self.ax.plot(time_arry, setpoint_arry, 'red', linewidth=3, label='Setpoint')
                self.ax.legend()    #loc='northeast'

        if self.hidpi_bool:
            self.ax.set_xlabel('Time [min]', fontsize=25)
            self.ax.set_ylabel(f'Temperature [\N{DEGREE CELSIUS}]', fontsize=20)
            self.ax.tick_params(axis='both', which='major', labelsize=20)
            self.ax.set_title('Temperature History', fontsize=35)
        else:
            self.ax.set_xlabel('Time [min]', fontsize=10)
            self.ax.set_ylabel(f'Temperature [\N{DEGREE CELSIUS}]', fontsize=10)
            self.ax.tick_params(axis='both', which='major', labelsize=10)
            self.ax.set_title('Temperature History', fontsize=14)

        self.ax.set_xlim(xlim)       # Set the current xlim to whatever was initialized in plt_scale_var
        self.ax.set_ylim(ylim)       # Compute the ylim based on the range of data being displayed

        self.canvas.draw()

    def reset_timebase(self):
        self.save_data_to_csv()     # Save the data before wiping the logs
        self.savefig()

        self.timebase = time.time()
        self.rel_time = 0

        self.history_time = []
        self.history_temp = []
        self.history_setpoint = []
        self.history_mode = []
        self.history_estop = []
        self.history_status = []

    def get_rel_time(self, frmt_bool=None):
        """
        Returns the minutes since the current timebase was initialized
        """

        sec_rel = (time.time() - self.timebase)
        if frmt_bool:
            return sec_rel/60, str(timedelta(seconds=sec_rel))[2:-4]    # Chops off the extra characters (don't need days or ms)
        else:
            return sec_rel/60     # Convert second to minutes

    def get_datetime_str(self):
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    def get_datetime_log(self):
        return datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    def set_setpoint(self, new_setpoint):
        if not self.estop_bool:
            if new_setpoint < 140:
                self.send_temp(self.ser_controller, new_setpoint)
            else:
                Messagebox.show_error('Please choose a setpoint less than 140 \N{DEGREE CELSIUS}', title='Max Setpoint Exceeded')
        else:
            Messagebox.show_error('System is estopped!', title='ESTOP Active')

    def send_temp(self, ser, temp):
        ser.write(bytes(f'<{round(temp, 5)}>', 'ascii'))    # Need to enclose temp in <> for the nonblocking parsefloat function on the arduino side

    def set_heater_indicator(self, heater_bool):
        if heater_bool:
            self.heater_canvas.itemconfig(self.status_indicator, fill='#2bed65')
            self.str_heater_status.set('HEATER ON')
        else:
            self.heater_canvas.itemconfig(self.status_indicator, fill='gray')
            self.str_heater_status.set('HEATER OFF')

    def preheat_bar(self, cmd):
        if cmd == 'on':
            if (self.lbl_preheat is None) and (self.prog_bar_preheating is None):    # System just entered preheat cycle
                self.lbl_preheat = ttk.Label(master=self.frm_status, text= 'Preheat status: ', font=f"-size {self.status_fsize}")
                self.lbl_preheat.grid(row=5, column=0, sticky='w')

                self.prog_bar_preheating = ttk.Progressbar(
                    master=self.frm_status,
                    orient=HORIZONTAL,
                    variable=self.flt_mean_temp,
                    maximum=self.flt_setpoint.get(),
                    bootstyle=(WARNING, STRIPED),
                )
                self.prog_bar_preheating.grid(row=5, column=1, sticky='ew')

        else:
            if (self.lbl_preheat is None) and (self.prog_bar_preheating is None):    # System just entered preheat cycle
                return
            else:
                self.lbl_preheat.destroy()
                self.prog_bar_preheating.destroy()
                self.lbl_preheat = None
                self.prog_bar_preheating = None

    def receive_controller_data_and_update(self, data_str):
        """
        Doubles as the serial parser and state manager while in a state
        The state transition manager handles the transistion between states in the function change_state
        
        """

        parse_args = data_str.split(' ')
        for i, arg in enumerate(parse_args[:6]):
            if arg == 'nan':
                if len(self.history_temp):
                    self.tc_readings[i] = self.history_temp[-1][i]     # If it's a nan, set it to value of the last temperature.
                else:
                    self.tc_readings[i] = 0     # Corner case if the nan is in the first entry in the history vector
                self.write_log(f'Nan detected in TC {i+1}')
            else:
                self.tc_readings[i] = float(parse_args[i])
        self.heater_is_active = int(parse_args[6])
        self.setpoint = float(parse_args[7])
        estop = int(parse_args[8])

        for idx, tc in enumerate(self.tc_strs):
            tc.set(f'{self.tc_readings[idx]} \N{DEGREE CELSIUS}')

        self.temp_mean = np.mean(self.tc_readings)
        self.temp_std = np.std(self.tc_readings, ddof=1)    # Sample standard deviation, not population std deviation

        self.flt_mean_temp.set(f'{round(self.temp_mean, 2)} \N{DEGREE CELSIUS}')
        self.flt_stddev.set(f'{round(self.temp_std, 2)} \N{DEGREE CELSIUS}')
        self.flt_setpoint.set(f'{round(self.setpoint, 2)} \N{DEGREE CELSIUS}')

        self.set_heater_indicator(self.heater_is_active)

        if (self.setpoint - self.temp_mean) > 5:    # System is heating    alternative: add logic AND so that it only says heating if both the temp is out of range and the heater is on
            self.str_action.set('Heating')
            self.preheat_bar('on')
        elif (self.temp_mean - self.setpoint) > 5:    # System is cooling
            self.str_action.set('Cooling')
            self.preheat_bar('off')
        else:
            self.str_action.set('Holding')
            self.preheat_bar('off')

        self.rel_time, self.str_rel_time = self.get_rel_time(frmt_bool=True)
        self.history_time.append(self.rel_time)
        self.history_temp.append(self.tc_readings.copy())
        self.history_setpoint.append(self.setpoint)
        self.history_mode.append(self.str_mode.get().split(' ')[0])
        self.history_status.append(self.str_status.get())
        self.history_estop.append(self.estop_bool)
        self.history_fan1.append(self.fan1_rpm)     # The fan RPMs are appended in the main controller loop so that the length of the list matches those for the other quantities
        self.history_fan2.append(self.fan2_rpm)

        if int(estop) and not self.estop_bool:      # Estop can be either 1 or 2 depending on the fault condition. Only calls the estop function once and not in subsequent loops. TODO log the fault condition
            self.on_estop()
            self.write_log(f'ESTOP CODE: {estop}')

        self.draw_plot()

        # Then start doing the routines for the state machine
        if 'MANUAL' in self.str_mode.get():
            self.str_mode.set(f'MANUAL {self.str_rel_time}')

        if 'AUTO' in self.str_mode.get():
            self.update_auto_seq()     # Update the auto sequence setpoint

    def receive_fan1_data(self, serial_str):
        self.fan1_rpm = int(serial_str)
        self.str_fan1.set(f'{self.fan1_rpm} RPM')

    def receive_fan2_data(self, serial_str):
        self.fan2_rpm = int(serial_str)
        self.str_fan2.set(f'{self.fan2_rpm} RPM')

    # "State machine" update functions - self.str_mode holds the current state
    def on_set_manual_setpoint(self):      # This is kind of like a state transistion manager
        if not self.entry_manual_setpoint.get():    # If the manual setpoint field was empty
            return

        if 'AUTO' in self.str_mode.get():
            self.on_abort_auto_seq()

        if 'MANUAL' not in self.str_mode.get(): # Only want to reset the timebase if manual mode is switched into from a different mode
            self.reset_timebase()

        setpoint = float(self.entry_manual_setpoint.get())
        self.set_setpoint(setpoint)
        self.str_mode.set(f'MANUAL {self.str_rel_time}')
        self.entry_manual_setpoint.delete(0, 'end')
        self.preheat_bar('off')
        self.str_status.set('RUNNING')
        self.lbl_status.config(foreground=app.status_colors['RUNNING'])
        self.write_log(f'Set manual setpoint: {setpoint}C')

    def on_start_auto_sequence(self):
        self.reset_timebase()

        self.str_mode.set(f'AUTO {self.str_rel_time}')
        self.preheat_bar('off')
        self.str_status.set('RUNNING')
        self.lbl_status.config(foreground=app.status_colors['RUNNING'])
        self.update_auto_seq(first_bool=True)  # First time through the auto sequence loop
        self.write_log('Starting autosequence')

        # Change start button to abort button
        self.btn_submit_seq_auto.destroy()
        self.btn_abort_seq_auto = ttk.Button(master=self.frm_auto, width=10, text="STOP", bootstyle=DANGER, command=self.on_abort_auto_seq)
        self.btn_abort_seq_auto.grid(row=1, column=1, padx=10, pady=10)
        self.btn_select_seq_auto.config(state=DISABLED)

    def on_abort_auto_seq(self):
        self.set_setpoint(0)
        self.str_mode.set('OFF')
        self.str_status.set('CONNECTED')
        self.lbl_status.config(foreground=self.status_colors['CONNECTED'])

        self.seq_minimap.lines.pop()    # Remove the last artist to avoid accumulating artists
        self.canvas_autoseq.draw()
        self.preheat_bar('off')
        self.write_log('Stopped autosequence')

        self.btn_abort_seq_auto.destroy()
        self.btn_submit_seq_auto = ttk.Button(master=self.frm_auto, width=10, text="START", bootstyle=SUCCESS, command=self.on_start_auto_sequence)
        self.btn_submit_seq_auto.grid(row=1, column=1, padx=10, pady=10)
        self.btn_select_seq_auto.config(state=NORMAL)

    def update_auto_seq(self, first_bool=False):
        # Tasks to run if sequence is over
        if self.rel_time > self.auto_sequence[-1,0]:
            self.set_setpoint(0)
            self.str_mode.set('OFF')
            self.str_status.set('CONNECTED')
            self.lbl_status.config(foreground=self.status_colors['CONNECTED'])
            self.btn_select_seq_auto.config(state=NORMAL)

        else:
            # Update the minimap
            minimap_plt_times = np.linspace(0, self.rel_time, endpoint=True, num=500)
            minimap_plt_temps = self.auto_sequence_interp(minimap_plt_times)
            if not first_bool:  # If you pop() on the first time through the loop, you erase the target setpoint plot
                self.seq_minimap.lines.pop()    # Remove the last artist to avoid accumulating artists
            self.seq_minimap.plot(minimap_plt_times, minimap_plt_temps, 'red')
            self.canvas_autoseq.draw()

            # If the last temp wasn't the same as the current temp, send a new setpoint
            target_setpoint_interp = float(self.auto_sequence_interp(np.array(self.rel_time)))
            if target_setpoint_interp != self.setpoint:
                self.set_setpoint(target_setpoint_interp)

            self.str_mode.set(f'AUTO {self.str_rel_time}')

    def save_data_to_csv(self):
        """
        Fields that are saved:
        Time
        temp
        setpoint
        mode
        status
        estop bool
        
        """

        if len(self.history_time):
            history_arry = np.column_stack((self.history_time, self.history_temp, self.history_setpoint, self.history_estop))
            header_str = 'Time [min], TC1 [degC], TC2 [degC], TC3 [degC], TC4 [degC], TC5 [degC], TC6 [degC], Setpoint [degC], Estop'
            fname = f'{self.data_dirname}/{self.get_datetime_str()}.csv'
            np.savetxt(fname, history_arry, delimiter=',', header=header_str)
            self.write_log(f'Wrote data to file: {fname}')

    def savefig(self):
        if len(self.history_time):
            fname = f'{self.data_dirname}/{self.get_datetime_str()}.png'
            self.fig_main_temp_plot.savefig(fname, dpi=400)
            self.write_log(f'Wrote data to file: {fname}')

def process_incoming_data():

    dev_connected_bool = False

    # Read from controller
    if app.controller_com_port_is_selected:
        dev_connected_bool = True

        try:
            line = app.ser_controller.readline()
        except Exception as e:
            app.write_log('---------- LOST CONNECTION WITH CONTROLLER ----------')
            app.str_status.set('INACTIVE')
            app.lbl_status.config(foreground=app.status_colors['INACTIVE'])
            app.selected_controller_comport.set('None')
            app.controller_com_port_is_selected = None
            app.str_mode.set('OFF')
            line = None

        if line:
            string = line.decode().strip('\r\n')  # convert the byte string to a unicode string
            app.receive_controller_data_and_update(string)

    if app.fan1_com_port_is_selected:
        dev_connected_bool = True

        try:
            line = app.ser_fan1.readline()
        except Exception as e:
            app.write_log('---------- LOST CONNECTION WITH Fan 1 ----------')
            line = None
        if line:
            string = line.decode().strip('\r\n')  # convert the byte string to a unicode string
            app.receive_fan1_data(string)

    if app.fan2_com_port_is_selected:
        dev_connected_bool = True
        try:
            line = app.ser_fan2.readline()
        except Exception as e:
            app.write_log('---------- LOST CONNECTION WITH Fan 2 ----------')
            line = None
        if line:
            string = line.decode().strip('\r\n')  # convert the byte string to a unicode string
            app.receive_fan2_data(string)

    if dev_connected_bool:
        app.after(50, process_incoming_data)   # A finite delay (~100) is needed to wait for other events to be captured (limitation of running single-threaded). Else, it will just read the serial port the whole time
    else:
        app.after(1000, process_incoming_data)

    if app.ports != serial.tools.list_ports.comports():     # The list of ports has changed, like after adding a device
        # Update the menu of possible COM ports

        # Controller
        app.ports = serial.tools.list_ports.comports()
        app.dev = [port.device for port in app.ports]

        app.menu_controller_com.destroy()
        app.mb_controller_com.destroy()

        app.menu_controller_com = ttk.Menu(app.root)
        for dev in app.dev:
            app.menu_controller_com.insert_radiobutton(label=dev, value=dev, variable=app.selected_controller_comport, index=0)

        app.mb_controller_com = ttk.Menubutton(
            master=app.frm_theme_selection,
            textvariable=app.selected_controller_comport,
            bootstyle=(SECONDARY, OUTLINE),
            menu=app.menu_controller_com)
        app.mb_controller_com.grid(row=0, column=3, padx=5, pady=5, sticky='w')

        # Fan 1
        app.menu_fan1_com.destroy()
        app.mb_fan1_com.destroy()

        app.menu_fan1_com = ttk.Menu(app.root)
        for dev in app.dev:
            app.menu_fan1_com.insert_radiobutton(label=dev, value=dev, variable=app.selected_fan1_comport, index=0)

        app.mb_fan1_com = ttk.Menubutton(
            master=app.frm_theme_selection,
            textvariable=app.selected_fan1_comport,
            bootstyle=(SECONDARY, OUTLINE),
            menu=app.menu_fan1_com)
        app.mb_fan1_com.grid(row=0, column=5, padx=5, pady=5, sticky='w')

        # Fan 2
        app.menu_fan2_com.destroy()
        app.mb_fan2_com.destroy()

        app.menu_fan2_com = ttk.Menu(app.root)
        for dev in app.dev:
            app.menu_fan2_com.insert_radiobutton(label=dev, value=dev, variable=app.selected_fan2_comport, index=0)

        app.mb_fan2_com = ttk.Menubutton(
            master=app.frm_theme_selection,
            textvariable=app.selected_fan2_comport,
            bootstyle=(SECONDARY, OUTLINE),
            menu=app.menu_fan2_com)
        app.mb_fan2_com.grid(row=0, column=7, padx=5, pady=5, sticky='w')


if __name__ == "__main__":
    hidpi_bool = True

    app = App("TRAK TRO 37 SMH Command, Control, and Monitoring Center", "iconic.png", hidpi_bool)
    
    app.after(0, process_incoming_data)
    app.mainloop()