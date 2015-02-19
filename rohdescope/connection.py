"""Provide the connection classes for the different kind of scopes."""

# Imports
import numpy
import vxi11
import threading
from timeit import default_timer as time


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

    def write(self, command):
        """Perform a write operation"""
        command = self.prepareCommand(command)
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

    def get_waveform_string(self, channels):
        """Return a string containing the waveform values
        for the given channels.

        Not implemented here.
        """
        raise NotImplementedError

    def parse_waveform_string(self, channels, string):
        """Return the waveform values as a dictionary.

        The channels argument are the channels included in the acquisition.
        The string argument is the data from the scope.
        """
        result = {}
        channel_number = len(channels)
        # Prepare string
        data_length_length = int(string[1])
        data_length = int(string[2:2+data_length_length])
        string = string[2+data_length_length]
        # Loop over channels
        for index, channel in enumerate(channels):
            substring = string[index:data_length:channel_number]
            result[channel] = numpy.fromstring(substring, dtype=numpy.int8)
        # Return dictionary
        return result

    def convert_waveforms(self, data_dict, scales=None, positions=None):
        """Convert the values in the acquisition dictionary
        to divisions or volts.

        If scales and positions are given, the result is returned in volts.
        Otherwise, the result is in divisions.
        """
        result = {}
        # Loop over the channels
        for channel, data in data_dict.items():
            # Get median
            info = numpy.iinfo(data.dtype)
            data_median = (info.max + info.min) * 0.5
            # Get factor and position
            factor = 10.0
            factor /= info.max - info.min
            if scales is not None:
                factor *= scales[channel]
            position = 0 if positions is None else positions[channel]
            # Convert
            data = data.astype(numpy.double)
            result[channel] = ((data - data_median) * factor) + position
        # Return dict
        return result

    def get_waveform_data(self, channels):
        """Return the waveform raw data as a dictionary
        for the given channels.
        """
        string = self.get_waveform_string(channels)
        return self.parse_wavefrom_data(channels, string)

    def get_waveforms(self, scales=None, positions=None):
        """Return the waveform values as a dictionary.

        The channels are the channels to include in the acquisition.
        """
        data_dict = self.get_wavefrom_data()
        return self.convert_waveforms(self, data_dict, scales, positions)

    def stamp_acquisition(self, channels):
        """Return the time stamp of an acquisition
        along with the values as a string.
        """
        self.scope.ask("RUNS;*OPC?")
        return time(), self.get_waveform_string(channels)

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

    def get_state(self):
        """Not implemented here."""
        raise NotImplementedError

    def get_status(self):
        """Not implemented here."""
        raise NotImplementedError

    # Time base accessor methods

    def get_time_scale(self):
        """Return the time scale in seconds/division."""
        cmd = "TIMebase:SCALe?"
        return float(self.ask(cmd))

    def set_time_scale(self, scale):
        """Set the time scale in seconds/division."""
        cmd = "TIMebase:SCALe {0}".format(scale)
        self.write(cmd)

    def get_time_range(self):
        """Return the time range in seconds."""
        cmd = "TIMebase:RANGe?"
        rng = self.ask(cmd)
        return float(rng)

    def set_time_range(self, time_range):
        """Set the time range in seconds (for the 10 divisions)."""
        cmd = "TIMebase:RANGe {0}".format(time_range)
        self.write(cmd)

    def get_time_position(self):
        """Return the time position in seconds."""
        cmd = "TIMebase:POSition?"
        rng = self.ask(cmd)
        return float(rng)

    def set_time_position(self, position):
        """Set the time position in seconds."""
        cmd = "TIMebase:POSition {0}".format(position)
        self.write(cmd)

    # Channel settings accessor methods

    def get_channel_offset(self, channel):
        """Return the offset for a given channel in volts."""
        cmd = "CHAN{0}:OFFSet?".format(channel)
        return float(self.ask(cmd))

    def set_channel_offset(self, channel, offset):
        """Set the offset for a given channel in volts."""
        cmd = "CHAN{0}:OFFSet {1}".format(channel, offset)
        self.write(cmd)

    def get_channel_position(self, channel):
        """Return the position for a given channel in volts."""
        cmd = "CHAN{0}:POSition?".format(channel)
        return float(self.ask(cmd))

    def set_channel_position(self, channel, position):
        """Set the position in volts for a given channel"""
        cmd = "CHAN{0}:POSition {1}".format(channel, position)
        self.write(cmd)

    def get_channel_range(self, channel):
        """Return the range for a given channel in volts."""
        cmd = "CHAN%s:RANGe?".format(channel)
        return float(self.ask(cmd))

    def set_channel_range(self, channel, channel_range):
        """Set the range for a given channel in volts."""
        cmd = "CHAN{0}:RANGe {1}".format(channel, channel_range)
        self.write(cmd)

    def get_channel_scale(self, channel):
        """Return the scale for a given channel in volts/division."""
        cmd = "CHAN%s:SCALe?".format(channel)
        return float(self.ask(cmd))

    def set_channel_scale(self, channel, scale):
        """Set the scale for a given channel in volts/division."""
        cmd = "CHAN{0}:SCALe {1}".format(channel, scale)
        self.write(cmd)

    def get_channel_coupling(self, channel):
        """Return the coupling for a given channel."""
        cmd = "CHAN{0}:COUPling?".format(channel)
        return str(self.ask(cmd))

    def set_channel_coupling(self, channel, coupling):
        """Set the coupling for a given channel.
        The value should be DC, DCL, DCLimit or AC
        """
        if coupling not in ['DC', 'DCL', 'DCLimit', 'AC']:
            raise ValueError('coupling type not allowed, '
                             'it should be DC, DCLimit, AC or GND')
        cmd = "CHAN{0}:COUPling {1}".format(channel, coupling)
        self.write(cmd)

    def get_channel_enabled(self, channel):
        """Return whether the given channel is enabled."""
        cmd = "CHAN{0}:STATe?".format(channel)
        state = int(self.ask(cmd))
        return bool(state)

    def set_channel_enabled(self, channel, enabled):
        """Enable or disable a given channel."""
        state = ("OFF", "ON")[bool(enabled)]
        cmd = "CHAN{0}:STATe {1}".format(channel, state)
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


# RTM scope connection class
class RTMConnection(ScopeConnection):
    """Connection class for the RTM scope."""

    # State accessors

    def get_state(self):
        """Return whether the scope is acquiring.
        This is a not really reliable work around.
        """
        cmd = "CHAN:HIST:CURR?"
        res = int(self.ask(cmd))
        return res <= 1

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

    # Waveform acquisition

    def get_waveform_string(self, channels):
        """Return a string containing the waveform values
        for the given channels.
        """
        result = []
        # Loop over channels
        for channel in channels:
            with self.lock:
                self.scope.write("CHAN{0}:DATA?".format(channel))
                result.append(self.scope.read_raw())
        # Return list
        return result

    def parse_waveform_string(self, channels, string):
        """Return the waveform values as a dictionary.

        The channels argument are the channels included in the acquisition.
        The string argument is the data from the scope.
        """
        result = {}
        # Loop over the channels
        for channel in channels:
            dct = ScopeConnection.parse_waveform_string([channel], string)
            result.update(dct)
        # Return dict
        return result


# RTO scope connection class
class RTOConnection(ScopeConnection):
    """Connection class for the RTM scope."""

    def connect(self):
        """Connect to the scope if not already connected."""
        # Call parent
        connected = self.connected
        ScopeConnection.connect(self)
        # Disable time values for acquisitions
        if not connected:
            cmd = "EXPort:WAVeform:INCXvalues OFF"
            self.scope.write(cmd)

    # State accessors

    def get_state(self):
        """Return whether the scope is acquiring."""
        # TODO
        pass

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

    # Fast acquisition

    def set_fast_readout(self, enabled):
        state = ("OFF", "ON")[bool(enabled)]
        cmd = "EXP:WAV:FAST {0}".format(state)
        self.write(cmd)

    def set_display(self, enabled):
        cmd = "EXP:WAV:DISP {0}".format(int(not enabled))
        self.write(cmd)

    # Waveform acquisition

    def get_waveform_string(self, channels):
        """Return a string containing the waveform values
        for the given channels.
        """
        with self.lock:
            self.scope.write("CHAN{0}:WAV1:DATA:VAL?".format(channels[0]))
            return self.scope.read_raw()
