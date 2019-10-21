from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import functools as ft
import logging
import pkgutil
import sys

try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass
from PySide2 import QtGui, QtCore, QtWidgets
from base_node_rpc.async import asyncio
from dropbot import EVENT_ENABLE, EVENT_CHANNELS_UPDATED, EVENT_SHORTS_DETECTED
from logging_helpers import _L
import blinker
import dropbot_monitor as dbm
import jinja2
import mistune
import numpy as np
import pandas as pd
import si_prefix as si

from ..invoker import Invoker


class DropBotStatusLabel(QtWidgets.QLabel):
    img_chip_removed = 'dropbot.png'
    img_chip_inserted = 'dropbot-chip-inserted.png'
    red = '#f15854'
    yellow = '#decf3f'
    green = '#60bd68'

    def __init__(self, *args, **kwargs):
        super(DropBotStatusLabel, self).__init__(*args, **kwargs)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self._chip_inserted = False
        self.connected = False
        self.setFixedSize(200, 160)

    @property
    def connected(self):
        return self._connected

    @connected.setter
    def connected(self, value):
        if not value:
            self._chip_inserted = False
        self._connected = value
        self._update_img()

    @property
    def chip_inserted(self):
        return self._chip_inserted

    @chip_inserted.setter
    def chip_inserted(self, value):
        self._chip_inserted = value
        self._update_img()

    def _update_img(self):
        if not self.connected:
            color = self.red
            filename = self.img_chip_removed
        elif self.chip_inserted:
            color = self.green
            filename = self.img_chip_inserted
        else:
            color = self.yellow
            filename = self.img_chip_removed
        self._set_img(filename)
        self.setStyleSheet('QLabel { background-color : %s ;  }' % color)

    def _set_img(self, filename):
        img_blob = pkgutil.get_data('dropbot_monitor.bin', 'images/%s' %
                                    filename)
        qpixmap_full = QtGui.QPixmap()
        qpixmap_full.loadFromData(img_blob)
        qpixmap = qpixmap_full.scaled(150, 150, QtCore.Qt.KeepAspectRatio)
        self.setPixmap(qpixmap)


class DropBotSettings(QtWidgets.QWidget):
    def __init__(self, signals, name='form'):
        super(DropBotSettings, self).__init__()
        self.name = name
        self.setFixedWidth(560)
        self.formGroupBox = QtWidgets.QGroupBox("DropBot")
        self.grid_layout = QtWidgets.QGridLayout()
        self.form_layout = QtWidgets.QFormLayout()
        self.dropbot_status = DropBotStatusLabel()
        connect_button = QtWidgets.QPushButton('&Connect')
        connect_button.setCheckable(True)
        self.monitor_task = None

        def on_connect_clicked():
            if connect_button.isChecked():
                self.monitor_task = dbm.monitor()
                self.monitor_task.signals.signal('capacitance-updated')\
                    .connect(self.on_capacitance_updated, weak=False)
                self.monitor_task.signals.signal('channels-updated')\
                    .connect(self.on_channels_updated, weak=False)
                self.monitor_task.signals.signal('connected')\
                    .connect(self.on_connected, weak=False)
                self.monitor_task.signals.signal('disconnected')\
                    .connect(self.on_disconnected, weak=False)
                self.monitor_task.signals.signal('chip-inserted')\
                    .connect(self.on_chip_inserted, weak=False)
                self.monitor_task.signals.signal('chip-removed')\
                    .connect(self.on_chip_removed, weak=False)
                connect_button.setText('&Disconnect')
            else:
                try:
                    self.monitor_task.stop()
                    self.monitor_task.cancel()
                except Exception:
                    _L().warning('could not cancel')
                self.capacitance_label.setText('-')
                self.voltage_label.setText('-')
                connect_button.setText('&Connect')
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self.on_disconnected(None))

        connect_button.clicked.connect(on_connect_clicked)

        self.form_layout.addRow(QtWidgets.QLabel("Connection:"),
                                connect_button)
        self.port_label = QtWidgets.QLabel('-')
        self.form_layout.addRow(QtWidgets.QLabel("Port:"), self.port_label)

        voltage_spin_box = QtWidgets.QDoubleSpinBox()
        voltage_spin_box.setRange(0, 150);
        voltage_spin_box.setValue(100)

        self.form_layout.addRow(QtWidgets.QLabel("Target voltage:"),
                                voltage_spin_box)
        self.capacitance_label = QtWidgets.QLabel('-')
        self.voltage_label = QtWidgets.QLabel('-')
        self.form_layout.addRow(QtWidgets.QLabel("Voltage:"),
                                self.voltage_label)
        self.form_layout.addRow(QtWidgets.QLabel("Capacitance:"),
                                self.capacitance_label)

        self.grid_layout.addLayout(self.form_layout, 0, 0)
        self.grid_layout.addWidget(self.dropbot_status, 0, 1)
        self.main_layout = QtWidgets.QGridLayout()
        self.formGroupBox.setLayout(self.grid_layout)
        self.main_layout.addWidget(self.formGroupBox, 0, 0)

        self.channels_box = ChannelsGrid(signals, 'Channels:')
        self.main_layout.addWidget(self.channels_box, 1, 0)

        self.setLayout(self.main_layout)

        def on_change(x):
            signals.signal('dropbot.voltage').send(name, value=x)

        voltage_spin_box.valueChanged.connect(on_change)
        self.voltage_spin_box = voltage_spin_box
        signals.signal('dropbot.voltage').connect(self.on_voltage_changed)
        signals.signal('dropbot.tooltip').connect(self.on_tooltip)
        signals.signal('actuate-channels').connect(self.on_actuate_channels)

        self.signals = signals

        connect_button.toggle()
        on_connect_clicked()

    def on_actuate_channels(self, channels):
        self.monitor_task.dropbot\
            .set_state_of_channels(pd.Series(1, index=channels), append=False)

    def on_tooltip(self, sender, **kwargs):
        self.dropbot_status.setToolTip(mistune.markdown(kwargs['text']))

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.WindowStateChange:
            if self.isMinimized():
                self.hide()
                return True

    @asyncio.coroutine
    def on_disconnected(self, sender, **message):
        self.port_label.setText('-')
        self.dropbot_status.connected = False
        self.voltage_spin_box.setValue(0)
        self._update_tooltip(None)

    @asyncio.coroutine
    def on_connected(self, sender, **message):
        number_of_channels = message['dropbot'].number_of_channels
        message['dropbot'].update_state(capacitance_update_interval_ms=250,
                                        hv_output_selected=True,
                                        hv_output_enabled=True,
                                        voltage=90,
                                        event_mask=EVENT_CHANNELS_UPDATED |
                                        EVENT_SHORTS_DETECTED |
                                        EVENT_ENABLE)

        def ui_code():
            self.dropbot_status.connected = True
            self.port_label.setText(message['dropbot'].port)
            self.voltage_spin_box.setValue(message['dropbot'].voltage)
            self._update_tooltip(message['dropbot'])
            self.channels_box.count = number_of_channels

        invoker.invoke(ui_code)

    def _update_tooltip(self, dropbot):
        template_str = pkgutil.get_data('dropbot_monitor.bin',
                                        'dropbot-status.md')
        template = jinja2.Template(template_str)
        tooltip_text = template.render(dropbot=dropbot,
                                       chip_inserted=self.dropbot_status
                                       .chip_inserted)
        self.signals.signal('dropbot.tooltip').send(self.name,
                                                    text=tooltip_text)

    def on_voltage_changed(self, sender, **message):
        if 'value' in message:
            try:
                self.monitor_task.dropbot.voltage = message['value']
            except Exception:
                _L().debug('error setting voltage', exc_info=True)

    @asyncio.coroutine
    def on_capacitance_updated(self, sender, **message):
        self.capacitance_label.setText('%sF' %
                                       si.si_format(message['new_value']))
        self.voltage_label.setText('%sV' % si.si_format(message['V_a']))

    @asyncio.coroutine
    def on_channels_updated(self, sender, **message):
        '''
        Message keys:
         - ``"n"``: number of actuated channels
         - ``"actuated"``: list of actuated channel identifiers.
         - ``"start"``: ms counter before setting shift registers
         - ``"end"``: ms counter after setting shift registers
        '''
        def ui_code():
            self.channels_box.actuated_channels = set(message['actuated'])

        invoker.invoke(ui_code)

    @asyncio.coroutine
    def on_chip_inserted(self, sender, **message):
        self.dropbot_status.chip_inserted = True
        self._update_tooltip(self.monitor_task.dropbot)

    @asyncio.coroutine
    def on_chip_removed(self, sender, **message):
        self.dropbot_status.chip_inserted = False
        self._update_tooltip(self.monitor_task.dropbot)

    @property
    def fields(self):
        return {self.layout.itemAt(i, QtWidgets.QFormLayout.LabelRole).widget()
                .text(): self.layout.itemAt(i, QtWidgets.QFormLayout.FieldRole)
                .widget() for i in range(self.layout.rowCount())}


def greatest_factors(N):
    '''Inspired by https://stackoverflow.com/a/28328782/345236'''
    sqrt_floor = int(np.sqrt(N))

    factor_a = sqrt_floor
    while N // factor_a != N / factor_a:
        factor_a -= 1
    factor_b = N // factor_a
    return tuple(sorted((factor_a, factor_b))[::-1])


class ChannelsGrid(QtWidgets.QGroupBox):
    GREY = '#f0f0f0'
    # GREEN = '#008000'
    GREEN = '#60bd68'

    def __init__(self, signals, *args, **kwargs):
        super(ChannelsGrid, self).__init__(*args, **kwargs)
        self.signals = signals
        # grid_layout = QtWidgets.QGridLayout()
        # self.setLayout(grid_layout)

    @property
    def count(self):
        return getattr(self, '_count', 0)

    def _actuated(self, i):
        return (self.layout().itemAt(i).widget().palette()
                .color(QtGui.QPalette.Background) == self.GREEN)

    @count.setter
    def count(self, count_):
        grid_layout = QtWidgets.QGridLayout()
        self.setLayout(grid_layout)

        rows, columns = greatest_factors(count_)
        for i in range(rows):
            for j in range(columns):
                i_ = i * columns + j
                button_ij = QtWidgets.QPushButton('%s' % i_)
                button_ij.setMinimumSize(35, 25)

                def on_click(i):
                    actuated_channels = self.actuated_channels
                    if i in actuated_channels:
                        actuated_channels.remove(i)
                    else:
                        actuated_channels.add(i)
                    self.signals.signal('actuate-channels')\
                        .send(actuated_channels)

                grid_layout.addWidget(button_ij, i, j)
                button_ij.clicked.connect(ft.partial(on_click, i_))

    @property
    def actuated_channels(self):
        grid_layout = self.layout()
        return set([i for i in range(grid_layout.count())
                    if self._actuated(i)])

    @actuated_channels.setter
    def actuated_channels(self, channels):
        grid_layout = self.layout()
        for i in range(grid_layout.count()):
            button_i = grid_layout.itemAt(i).widget()
            channel_i = int(button_i.text())
            colour_i = self.GREEN if channel_i in channels else self.GREY
            button_i.setStyleSheet('QPushButton { background-color: %s; }' %
                                   colour_i)


def main():
    def show():
        settings.setWindowState(settings.windowState() &
                                ~QtCore.Qt.WindowMinimized |
                                QtCore.Qt.WindowActive)
        settings.show()

    def __icon_activated(reason):
        if reason in (QtWidgets.QSystemTrayIcon.DoubleClick, ):
            if settings.isVisible():
                settings.hide()
            else:
                show()


    signals = blinker.Namespace()
    settings = DropBotSettings(signals)

    def get_icon(filename):
        icon_blob = pkgutil.get_data('dropbot_monitor.bin', filename)
        qpixmap = QtGui.QPixmap()
        qpixmap.loadFromData(icon_blob)
        return QtGui.QIcon(qpixmap)

    # Colour icon for app window.
    window_icon = get_icon('sci-bots.ico')
    settings.setWindowIcon(window_icon)
    settings.setWindowTitle('DropBot status')

    # White logo for system tray.
    tray_icon = get_icon('images/sci-bots-white-logo-disconnected.ico')
    tray = QtWidgets.QSystemTrayIcon(settings)
    tray.setIcon(tray_icon)

    tray.activated.connect(__icon_activated)

    # Context Menu
    ctmenu = QtWidgets.QMenu()
    actionshow = ctmenu.addAction("Show/Hide")
    actionshow.triggered.connect(lambda: settings.hide()
                                 if settings.isVisible() else show())
    actionquit = ctmenu.addAction("Quit")
    actionquit.triggered.connect(settings.close)

    @asyncio.coroutine
    def on_connected(sender, **message):
        def ui_code():
            tray.showMessage('DropBot connected', 'Connected to DropBot on '
                             'port %s' % message['dropbot'].port,
                             tray.MessageIcon.Information)
            tray.setToolTip('DropBot connected')

        invoker.invoke(ui_code)

    settings.monitor_task.signals.signal('connected')\
        .connect(on_connected, weak=False)

    @asyncio.coroutine
    def on_disconnected(sender, **message):
        tray.showMessage('DropBot disconnected', 'Disconnected from DropBot.',
                         QtWidgets.QSystemTrayIcon.MessageIcon.Warning)
        tray_icon = get_icon('images/sci-bots-white-logo-disconnected.ico')
        tray.setIcon(tray_icon)
        tray.setToolTip('No DropBot connection')

    settings.monitor_task.signals.signal('disconnected')\
        .connect(on_disconnected, weak=False)

    @asyncio.coroutine
    def on_chip_inserted(sender, **message):
        tray_icon = get_icon('images/sci-bots-white-logo-chip-inserted.ico')
        port = settings.monitor_task.dropbot.port

        def ui_code():
            tray.setIcon(tray_icon)
            tray.setToolTip('DropBot connected (%s) - chip inserted' % port)

        invoker.invoke(ui_code)

    settings.monitor_task.signals.signal('chip-inserted')\
        .connect(on_chip_inserted, weak=False)

    @asyncio.coroutine
    def on_chip_removed(sender, **message):
        tray_icon = get_icon('images/sci-bots-white-logo-chip-removed.ico')
        tray.setIcon(tray_icon)
        port = settings.monitor_task.dropbot.port
        tray.setToolTip('DropBot connected (%s) - no chip inserted' % port)

    settings.monitor_task.signals.signal('chip-removed')\
        .connect(on_chip_removed, weak=False)

    tray.setContextMenu(ctmenu)
    tray.show()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = QtWidgets.QApplication(sys.argv)
    main()
    invoker = Invoker()
    sys.exit(app.exec_())
