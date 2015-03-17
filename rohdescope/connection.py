"""Provide the connection classes for the different kind of scopes."""

# Imports
import numpy
import vxi11
import threading
from functools import wraps
from collections import Mapping
from timeit import default_timer as time
from vxi11.vxi11 import Vxi11Exception


# Decorator to support the anbled channel dictionary
def support_channel_dict(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            channels = args[0]
        except IndexError:
            channels = kwargs.pop("channels", None)
        if isinstance(channels, Mapping):
            channels = sorted(key for key, value in channels.items()
                              if value)
            args = (channels,) + args[1:]
        return func(self, *args, **kwargs)
    return wrapper


# Scope connection class
class ScopeConnection(object):
    """Generic rohde scope connection object."""

    # Channel names (indexable)
    channel_names = [None, "channel1", "channel2",
                     "channel3", "channel4", "external"]

    # Trigger name
    trigger_name = "trigger"

    # Data format
    data_format = "uint8"

    def __init__(self, host, **kwargs):
        self._host = host
        self._kwargs = kwargs
        self.lock = threading.Lock()
        self.firmware_version = None
        self.scope = None

    # Connection methods

    def connect(self):
        """Connect to the scope if not already connected."""
        connected = self.connected
        # Instanciate the vxi11 instrument
        if not self.scope:
            self.scope = vxi11.Instrument(self._host, **self._kwargs)
        # Get firmware_version
        if not self.firmware_version:
            self.firmware_version = self.get_firmware_version()
        # Configure the scope
        if not connected:
            self.configure()

    def disconnect(self):
        """Disconnect from the scope if not already disconnected."""
        if self.scope:
            with self.lock:
                self.scope.close()
        self.scope = None
        self.firmware_version = None

    @property
    def connected(self):
        """Property to indicate whether the device is connected."""
        return self.scope and self.firmware_version

    def get_firmware_version(self):
        """Get the firmware version."""
        if not self.scope:
            raise RuntimeError("Vxi11 Instrument not instanciated.")
        with self.lock:
            idn = self.scope.ask("*IDN?")
        company, line, model, fw = idn.split(",")
        return tuple(int(part) for part in fw.split("."))

    def configure(self):
        """Configure the scope if it requires some custom settings."""
        self.clear_buffer()

    # Operation methods

    def ask(self, commands):
        """Prepare and run a command list"""
        if not self.connected:
            raise RuntimeError("not connected to the scope")
        command = self.prepare_command(commands)
        with self.lock:
            answer = self.scope.ask(command)
        return answer

    def write(self, command):
        """Perform a write operation"""
        if not self.connected:
            raise RuntimeError("not connected to the scope")
        command = self.prepare_command(command)
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
        cmd = "FORMAT:DATA " + self.data_format
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

    def issue_command(self, command):
        """Ask or write a command depending on its format."""
        command = command.strip()
        if command.endswith("?"):
            return self.ask(command)
        return self.write(command) or "Write command OK."

    def clear_buffer(self):
        """Clear the error buffer."""
        cmd = '*CLS'
        self.write(cmd)

    # Acquisition

    @support_channel_dict
    def get_waveform_string(self, channels):
        """Return a string containing the waveform values
        for the given channels.

        Not implemented here.
        """
        raise NotImplementedError

    @support_channel_dict
    def parse_waveform_string(self, channels, string):
        """Return the waveform values as a dictionary.

        The channels argument are the channels included in the acquisition.
        The string argument is the data from the scope.
        """
        result = {}
        channel_number = len(channels)
        if not channel_number or not string:
            return result
        # Prepare string
        dtype = self.data_format.replace(',', '').lower()
        data_length_length = int(string[1])
        data_length = int(string[2:2+data_length_length])
        string = string[2+data_length_length:]
        # Loop over channels
        for index, channel in enumerate(channels):
            substring = string[index:data_length:channel_number]
            result[channel] = numpy.fromstring(substring, dtype=dtype)
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
            # Get factor
            factor = 10.0
            factor /= info.max - info.min
            if scales is not None:
                factor *= scales[channel]
            # Get position
            position = 0
            if positions is not None:
                position = positions[channel] * scales[channel]
            # Convert
            data = data.astype(numpy.double)
            result[channel] = ((data - data_median) * factor) - position
        # Return dict
        return result

    def get_waveform_data(self, channels):
        """Return the waveform raw data as a dictionary
        for the given channels.
        """
        string = self.get_waveform_string(channels)
        return self.parse_waveform_string(channels, string)

    def get_waveforms(self, channels, scales=None, positions=None):
        """Return the waveform values as a dictionary.

        The channels are the channels to include in the acquisition.
        """
        data_dict = self.get_waveform_data(channels)
        return self.convert_waveforms(data_dict, scales, positions)

    def stamp_acquisition(self, channels, single=True, busy=True):
        """Return the time stamp of an acquisition
        along with the values as a string.
        """
        if channels and single:
            self.write("RUNS")
            self.wait(busy)
        return time(), self.get_waveform_string(channels)

    def wait(self, busy=True):
        """Wait for the last commands to complete."""
        # Use hardware wait
        if not busy:
            return self.ask("RUNS;*OPC?")
        # Prepare wait
        finished = lambda: int(self.ask("*ESR?")) % 2
        timeout = self._kwargs['instrument_timeout'] / 1000.0
        timeout += time()
        self.write("*OPC")
        # Wait for the commands to complete
        while not finished():
            # Handle timeout
            if time() > timeout:
                raise Vxi11Exception(15, "wait")

    # General accessor methods

    def get_identifier(self):
        """Return the scope identifier."""
        return str(self.ask("*IDN?"))

    def get_waveform_mode(self, channel):
        """Return the waveform mode."""
        cmd = "CHAN{0}:TYPE?".format(channel)
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

    def get_record_length(self):
        """Return the record length in points."""
        cmd = "ACQuire:POINts?"
        return int(self.ask(cmd))

    def set_record_length(self, length):
        """Set the record length in points."""
        cmd = "ACQuire:POINts {0}".format(length)
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
        """Return the position for a given channel in divisions."""
        cmd = "CHAN{0}:POSition?".format(channel)
        return float(self.ask(cmd))

    def set_channel_position(self, channel, position):
        """Set the position in divisions for a given channel"""
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
        cmd = "CHAN{0}:SCALe?".format(channel)
        return float(self.ask(cmd))

    def set_channel_scale(self, channel, scale):
        """Set the scale for a given channel in volts/division."""
        cmd = "CHAN{0}:SCALe {1}".format(channel, scale)
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

    def get_channel_coupling(self, channel):
        """Return the trigger coupling.
        (0 for DC, 1 for AC, 2 for DCLimit, 3 for ACLimit)
        """
        lst = ['DC', 'AC', 'DCL', 'ACL']
        cmd = "CHAN{0}:COUPLing?".format(channel)
        return lst.index(self.ask(cmd))

    def set_channel_coupling(self, channel, coupling):
        """Set the channel coupling.
        (0 for DC, 1 for AC, 2 for DCLimit, 3 for ACLimit)
        """
        lst = ['DC', 'AC', 'DCL', 'ACL']
        cmd = "CHAN{0}:COUPLing {1}".format(channel, lst[coupling])
        self.write(cmd)

    # Trigger operation

    def get_trigger_source(self):
        """Return the trigger source (1 to 4 for channels, 5 for external)."""
        cmd = self.trigger_name + ":SOUR?"
        channel = self.ask(cmd)
        return int(self.channel_names.index(channel))

    def set_trigger_source(self, channel):
        """Set the trigger source (1 to 4 for channels, 5 for external)."""
        cmd = self.trigger_name
        cmd += ":SOUR {0}".format(self.channel_names[channel])
        self.write(cmd)

    def get_trigger_level(self, channel):
        """Return the trigger level for a given channel in volts."""
        cmd = self.trigger_name + ":LEV{0}?".format(channel)
        return float(self.ask(cmd))

    def set_trigger_level(self, channel, value):
        """Set the trigger level for a given channel in volts."""
        cmd = self.trigger_name + ":LEV{0} {1}".format(channel, value)
        self.write(cmd)

    def get_trigger_slope(self):
        """Return the trigger slope.
        (0 for negative, 1 for positive and 2 for either)
        """
        lst = ['NEG', 'POS', 'EITH']
        cmd = self.trigger_name + ":EDGE:SLOPE?"
        return lst.index(self.ask(cmd))

    def set_trigger_slope(self, slope):
        """Set the trigger slope.
        (0 for negative, 1 for positive and 2 for either)
        """
        lst = ['NEG', 'POS', 'EITH']
        cmd = self.trigger_name + ":EDGE:SLOPE {0}".format(lst[slope])
        self.write(cmd)

    def get_trigger_coupling(self):
        """Return the trigger coupling.
        (0 for DC, 1 for AC, 2 for HF)
        """
        lst = ['DC', 'AC', 'HF']
        cmd = self.trigger_name + ":EDGE:COUPLing?"
        return lst.index(self.ask(cmd))

    def set_trigger_coupling(self, coupling):
        """Set the trigger coupling.
        (0 for DC, 1 for AC, 2 for HF)
        """
        lst = ['DC', 'AC', 'HF']
        cmd = self.trigger_name + ":EDGE:COUPLing {0}".format(lst[coupling])
        self.write(cmd)


# RTM scope connection class
class RTMConnection(ScopeConnection):
    """Connection class for the RTM scope."""

    # Channel names (indexable)
    channel_names = [None, "CH1", "CH2", "CH3", "CH4", "EXT"]

    # Trigger name
    trigger_name = "TRIG:A"

    # Data format
    data_format = "UINT,8"

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
        status_dict = {2**3: "Waiting for trigger.",
                       2**2: "Autosetting.",
                       2**1: "Self-testing.",
                       2**0: "Aligning.",
                       0:    "Status OK."}
        cmd = "STATus:OPER:COND?"
        code = int(self.ask(cmd)) % (2**4)
        default_code = "Unknown code: {0}".format(code)
        return status_dict.get(code, default_code)

    # Waveform acquisition

    def set_record_length(self, length):
        """Set the record length in points."""
        raise NotImplementedError

    @support_channel_dict
    def get_waveform_string(self, channels):
        """Return a string containing the waveform values
        for the given channels.
        """
        result = []
        # Loop over channels
        for channel in channels:
            with self.lock:
                cmd = "CHAN{0}:DATA?".format(channel)
                self.scope.write(cmd)
                result.append(self.scope.read_raw())
        # Return list
        return result

    @support_channel_dict
    def parse_waveform_string(self, channels, strings):
        """Return the waveform values as a dictionary.

        The channels argument are the channels included in the acquisition.
        The strings argument is the data from the scope.
        """
        result = {}
        # Loop over the channels
        for channel, string in zip(channels, strings):
            parent = super(RTMConnection, self)
            dct = parent.parse_waveform_string([channel], string)
            result.update(dct)
        # Return dict
        return result

    def stamp_acquisition(self, channels, single=False):
        """Return the time stamp of an acquisition
        along with the values as a string.
        """
        return super(RTMConnection, self).stamp_acquisition(channels, single)


# RTO scope connection class
class RTOConnection(ScopeConnection):
    """Connection class for the RTM scope."""

    # Channel names (indexable)
    channel_names = [None, "CHAN1", "CHAN2", "CHAN3", "CHAN4", "EXT"]

    # Trigger name
    trigger_name = "TRIG"

    # Data format
    data_format = "INT,8"

    # State accessors

    def get_state(self):
        """Return whether the scope is acquiring."""
        # TODO
        pass

    def get_status(self):
        """Return the status of the scope as a string."""
        status_dict = {2**4: "Measuring.",
                       2**3: "Waiting for trigger.",
                       24:   "Waiting for trigger.",
                       2**2: "Autosetting.",
                       2**1: "Calibrating.",
                       2**0: "Calibrating.",
                       0:    "Status OK."}
        cmd = "STATus:OPER:COND?"
        code = int(self.ask(cmd)) % (2**5)
        default_code = "Unknown code: {0}".format(code)
        return status_dict.get(code, default_code)

    # Fast acquisition

    def configure(self):
        """Configure the scope for fast acquisition mode."""
        # Clear the buffer
        super(RTOConnection, self).configure()
        # Do not include time values when reading the waveforms
        cmd = "EXPort:WAVeform:INCXvalues OFF"
        self.write(cmd)
        # Multichannel mode for fast export
        cmd = "EXPort:WAVeform:MULTichannel ON"
        self.write(cmd)
        # Set the fast binary readout
        self.set_fast_readout(True)
        self.set_binary_readout()

    def set_channel_export(self, channel, export):
        """Set the channel export for fast acquisition."""
        state = ("OFF", "ON")[bool(export)]
        cmd = "CHANnel{0}:EXPortstate {1}".format(channel, state)
        self.write(cmd)

    def get_channel_enabled(self, channel):
        """Update the channel export at every read of the channel state."""
        result = super(RTOConnection, self).get_channel_enabled(channel)
        self.set_channel_export(channel, result)
        return result

    def set_fast_readout(self, enabled):
        state = ("OFF", "ON")[bool(enabled)]
        cmd = "EXP:WAV:FAST {0}".format(state)
        self.write(cmd)

    def set_display(self, enabled):
        cmd = "EXP:WAV:DISP {0}".format(int(not enabled))
        self.write(cmd)

    # Waveform acquisition

    def set_record_length(self, length):
        """Set the record length in points."""
        cmd = "ACQuire:POINts:AUTO RECL"
        self.write(cmd)
        return super(RTOConnection, self).set_record_length(length)

    @support_channel_dict
    def get_waveform_string(self, channels):
        """Return a string containing the waveform values
        for the given channels.
        """
        if not channels:
            return ""
        with self.lock:
            self.scope.write("CHAN{0}:WAV1:DATA:VAL?".format(channels[0]))
            return self.scope.read_raw()

    # Time position correction

    def get_time_position(self):
        """Return the time position in seconds."""
        # Get position
        cmd = "TIMebase:HORizontal:POSition?"
        position = float(self.ask(cmd))
        # Get reference
        cmd = "TIMebase:REFerence?"
        shift = 0.5 - float(self.ask(cmd)) / 100
        # Get time range
        if shift:
            cmd = "TIMebase:RANGe?"
            position += shift * float(self.ask(cmd))
        return position

    def set_time_position(self, position):
        """Set the time position in seconds."""
        cmd = "TIMebase:REFerence {0}".format(50)
        self.write(cmd)
        cmd = "TIMebase:HORizontal:POSition {0}".format(position)
        self.write(cmd)

    def get_trigger_coupling(self):
        """Return the trigger coupling.
        (0 for DC, 1 for AC, 2 for DCLimit)
        """
        lst = ['DC', 'AC', 'DCL', 'ACL']
        cmd = self.trigger_name + ":ANEDge:COUPLing?"
        return lst.index(self.ask(cmd))

    def set_trigger_coupling(self, coupling):
        """Set the trigger coupling.
        (0 for DC, 1 for AC, 2 for DCLimit)
        """
        lst = ['DC', 'AC', 'DCL', 'ACL']
        cmd = self.trigger_name + ":ANEDge:COUPLing {0}".format(lst[coupling])
        self.write(cmd)
