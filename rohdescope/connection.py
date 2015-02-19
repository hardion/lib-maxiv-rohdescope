"""Provide the connection classes for the different kind of scopes."""

# Imports
import vxi11
import threading
import numpy as np


# Scope connection class
class ScopeConnection:
    """Generic rohde scope connection object."""

    def __init__(self, host, **kwargs):
        self._host = host
        self._kwargs = kwargs
        self.lock = threading.Lock()
        self.firmware_version = None
        self.scope = None

    # Connection methods

    def connect(self):
        """Connect to the scope if not already connected."""
        if not self.scope:
            self.scope = vxi11.Instrument(self._host, **self._kwargs)
        if not self.firmware_version:
            self.firmware_version = self.get_firmware_version()

    def disconnect(self):
        """Disconnect from the scope if not already disconnected."""
        if self.scope:
            self.scope.close()
        self.scope = None
        self.firmware_version = None

    @property
    def connected(self):
        """Property to indicate whether the device is connected."""
        return self.scope and self.firmware_version

    def get_firmware_version(self):
        """Get the firmware version."""
        idn = self.ask("*IDN?")
        company, line, model, fw = idn.split(",")
        return tuple(int(part) for part in fw.split("."))

    # Operation methods

    def ask(self, commands):
        """Prepare and run a command list"""
        command = self.prepare_command(commands)
        with self.lock:
            answer = self.scope.ask(command)
        return answer

    def write(self, commandList):
        """Perform a write operation"""
        command = self.prepareCommand(commandList)
        with self.lock:
            self.scope.write(command)

    def prepare_command(self, commands):
        """Generate a single command from a command list."""
        if isinstance(commands, str):
            return commands
        return ";".join(commands)

    # Acquisition settings

    def set_binary_readout(self):
        """Set the output format to binary."""
        cmd = "FORMAT:DATA UINT,8"
        self.write(cmd)

    def set_acquisition_count(self, count):
        """Set number of acquisition to average
        when performing a single acquisition.
        """
        cmd = "ACQ:NSIN:COUNT %d" % count
        self.write(cmd)

    # Commands

    def issue_reset(self):
        """Run the reset command."""
        cmd = "*RST"
        self.write(cmd)

    def issue_autoset(self):
        """Run the autoset command."""
        cmd = "AUT"
        self.write(cmd)

    def issue_run(self):
        """Run the command to start continuous acquisiton."""
        cmd = "RUN"
        self.write(cmd)

    def issue_stop(self):
        """Run the command to stop acquiring."""
        cmd = "STOP"
        self.write(cmd)

    # Acquisition

    def acquire_waveforms(self):
        """Acquire waveforms."""
        # Single acquisition case
        if single:
            with self.mutex:
                cmd = "SING;*OPC?"
                self.scope.write(cmd)
                self.scope.read_raw()
        # Get the waveforms
        return self.get_waveforms(division)

    def get_waveforms(self, division=True, volt=False, both=True):
        """Get the waveform dict."""
        decoded_waves = {}
        for channel in range(1, 5):
            decoded_waves[channel] = self.getWaveform(channel, division)
        return decoded_waves

    def getWaveform(self, channel, division=True):
        """Get the waveform for a given channel."""
        with self.mutex:
            # Get the record length
            self.scope.write("CHAN%d:DATA:POINTS?" % channel)
            points = int(self.scope.read_raw())
            # No data available
            if not points:
                return []
            # Get the data
            self.scope.write("CHAN%d:DATA?" % channel)
            wfdata = self.scope.read_raw()
            # Division mode
            if division:
                return self.decodeWaveform(wfdata, points)
            # Volt mode
            self.scope.write("CHAN%d:DATA:YOR?"  % channel)
            zero = float(self.scope.read_raw())
            self.scope.write("CHAN%d:DATA:YINC?"  % channel)
            inc = float(self.scope.read_raw())
            return self.decodeWaveform(wfdata, points, zero, inc)

    def decodeWaveform(self, data, wavlen, zero=None, inc=None):
        """Decode the given waveform."""
        # Note: we're assuming that the data has the correct format; (INT,8)
        lenlen = int(data[1])
        datalen = int(data[2:2+lenlen])

        if datalen != wavlen:
            msg = "Wrong number of points ({0} != {1})"
            raise ValueError(msg.format(datalen, wavlen))

        wave_data = np.fromstring(data[2+lenlen:-1], dtype=np.uint8)
        # Selected unit is division
        if zero is None or inc is None:
            nb_div = 10
            info = np.iinfo(wave_data.dtype)
            data_range = float(info.max - info.min)
            data_median = (info.max + info.min) * 0.5
            # Newer numpy version
            try: wave_data = wave_data.astype(np.double, copy=False)
            # Older numpy version
            except TypeError: wave_data = wave_data.astype(np.double)
            return (wave_data - data_median)* (nb_div / data_range)
        # Selected unit is volts
        else:
            return zero + (inc * wave_data)

    # General accessor methods

    def get_identifier(self):
        """Return the scope identifier."""
        return str(self.ask("*IDN?"))

    def get_record_length(self):
        """Return the number of points."""
        cmd = "ACQ:POINts?"
        return int(self.ask(cmd))

    def get_waveform_mode(self, chan):
        """Return the waveform mode."""
        cmd = "CHAN%d:TYPE?" % chan
        return str(self.ask(cmd))

    def get_acquire_mode(self):
        """Return le mode d'acquisition."""
        cmd = "ACQUIRE:MODE?"
        return str(self.ask(cmd))

    def get_status(self):
        """Return the status of the scope as a string."""
        status_dict = {8: "Stopped or waiting for trigger.",
                       4: "Autosetting.",
                       1: "Calibrating.",
                       0: "Status OK."}
        cmd = "STATus:OPER:COND?"
        code = int(self.ask(cmd))
        default_code = "Unknown code: {0}".format(code)
        return status_dict.get(code, default_code)

    # Time base accessor methods

    def get_time_scale(self):
        """Return the time scale in seconds/division."""
        cmd = "TIMebase:SCALe?"
        return float(self.ask(cmd))

    def get_time_range(self):
        """Return the time range in seconds."""
        cmd = "TIMebase:RANGe?"
        rng = self.ask(cmd)
        return float(rng)

    def get_time_position(self):
        """Return the time position in seconds."""
        cmd = "TIMebase:POSition?"
        rng = self.ask(cmd)
        return float(rng)

    # Channel settings accessor methods

    def get_channel_offset(self, channel):
        """Return the offset for a given channel in volts."""
        cmd = "CHAN{0}:OFFSet?".format(channel)
        return float(self.ask(cmd))

    def get_channel_position(self, channel):
        """Return the position for a given channel in volts."""
        cmd = "CHAN{0}:POSition?".format(channel)
        return float(self.ask(cmd))

    def get_channel_range(self, channel):
        """Return the range for a given channel in volts."""
        cmd = "CHAN%s:RANGe?".format(channel)
        return float(self.ask(cmd))

    def get_channel_scale(self, channel):
        """Return the scale for a given channel in volts/division."""
        cmd = "CHAN%s:SCALe?".format(channel)
        return float(self.ask(cmd))

    def get_coupling(self, channel):
        """Return the coupling for a given channel."""
        cmd = "CHAN{0}:COUPling?".format(channel)
        return str(self.ask(cmd))

    def get_channel_enabled(self, channel):
        cmd = "CHAN{0}:STATe?".format(channel)
        state = int(self.ask(cmd))
        return bool(state)

    # Custom setter methods

    def set_channel_enabled(self, channel, enabled):
        state = ("OFF", "ON")[bool(enabled)]
        self.write(":CHAN{0}:STATe {1}".format(channel, state))

    def set_channel_position(self, channel, position):
        cmd = "CHAN{0}:POSition {1}" % (chan, position)
        self.write(cmd)

    def setVScale(self, chan, sca):
        cmd = "CHAN%d:SCALe %f" % (chan, sca)
        self.write(cmd)

    def setHRange(self, rng):
        "Set the width of the whole display, i.e. 10*scale"
        cmd = "TIMebase:RANGe %s" % rng
        self.write(cmd)

    def setHPosition(self, pos):
        "Set the width of the whole display, i.e. 10*scale"
        cmd = "TIMebase:POSition %s" % pos
        self.write(cmd)

    def setCoupling(self, channel, coupling):
        if coupling not in ['DC', 'DCL', 'DCLimit', 'AC']:
            raise ValueError('coupling type not allowed, '
                             'it should be DC, DCLimit, AC or GND')
        cmd = "CHAN{0}:COUPling {1}".format(channel, coupling)
        self.write(cmd)

    # Trigger operation

    def get_trigger_source(self):
        """Return the trigger source (1 to 4 for channels, 5 for external)."""
        names = [None, "CH1", "CH2", "CH3", "CH4", "EXT"]
        cmd = "TRIG:A:SOUR?"
        channel = self.ask(cmd)
        return int(names.index(channel))

    def set_trigger_source(self, channel):
        """Set the trigger source (1 to 4 for channels, 5 for external)."""
        names = [None, "CH1", "CH2", "CH3", "CH4", "EXT"]
        cmd = "TRIG:A:SOUR {0}".format(names[channel])
        self.write(cmd)

    def get_trigger_level(self, channel):
        """Return the trigger level for a given channel in volts."""
        cmd = "TRIG:A:LEV{0}?".format(channel)
        return float(self.ask(cmd))

    def set_trigger_level(self, channel, value):
        """Set the trigger level for a given channel in volts."""
        cmd = "TRIG:A:LEV{0} {1}".format(channel, value)
        self.write(cmd)

    def get_trigger_slope(self):
        """Return the trigger slope.
        (0 for negative, 1 for positive and 2 for either)
        """
        lst = ['NEG', 'POS', 'EITH']
        cmd = "TRIG:A:EDGE:SLOPE?"
        return lst.index(self.ask(cmd))

    def set_trigger_slope(self, slope):
        """Set the trigger slope.
        (0 for negative, 1 for positive and 2 for either)
        """
        lst = ['NEG', 'POS', 'EITH']
        cmd = "TRIG:A:EDGE:SLOPE %s" % lst[slope]
        self.write(cmd)


class RTMConnection(ScopeConnection):
    """Connection class for the RTM scope."""

    def get_state(self):
        """Return whether the scope is acquiring.
        This is a not really reliable work around.
        """
        cmd = "CHAN:HIST:CURR?"
        res = int(self.ask(cmd))
        return res <= 1
