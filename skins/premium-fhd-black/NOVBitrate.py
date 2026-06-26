from __future__ import absolute_import
import threading, time, ctypes, struct, os, select as _sel
from enigma import eTimer, iServiceInformation
from Components.Converter.Converter import Converter
from Components.Element import cached

_libc = ctypes.CDLL("libc.so.6", use_errno=True)
_libc.ioctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_void_p]
_libc.ioctl.restype = ctypes.c_int

_DMX_SET_PES_FILTER  = 0x40146F2C
_DMX_IN_FRONTEND     = 0
_DMX_OUT_TS_TAP      = 2
_DMX_PES_OTHER       = 20
_DMX_IMMEDIATE_START = 4

def _measure_bitrate(adapter, demux, vpid, measure_secs=1.5):
    """Measure video PID bitrate via DMX_OUT_TS_TAP -> dvr0. Returns kbps or 0."""
    if vpid <= 0:
        return 0
    dmx_path = "/dev/dvb/adapter%d/demux%d" % (adapter, demux)
    dvr_path = "/dev/dvb/adapter%d/dvr0" % adapter
    fd_dmx = fd_dvr = -1
    try:
        fd_dmx = os.open(dmx_path, os.O_RDWR | os.O_NONBLOCK)
        buf = (ctypes.c_uint8 * 20)()
        struct.pack_into("<H", buf, 0, vpid)
        struct.pack_into("<I", buf, 4, _DMX_IN_FRONTEND)
        struct.pack_into("<I", buf, 8, _DMX_OUT_TS_TAP)
        struct.pack_into("<I", buf, 12, _DMX_PES_OTHER)
        struct.pack_into("<I", buf, 16, _DMX_IMMEDIATE_START)
        if _libc.ioctl(fd_dmx, _DMX_SET_PES_FILTER, ctypes.cast(buf, ctypes.c_void_p)) != 0:
            return 0
        fd_dvr = os.open(dvr_path, os.O_RDONLY | os.O_NONBLOCK)
        total = 0
        t0 = time.monotonic()
        while time.monotonic() - t0 < measure_secs:
            remaining = measure_secs - (time.monotonic() - t0)
            rds, _, _ = _sel.select([fd_dvr], [], [], min(remaining, 0.3))
            if rds:
                try:
                    total += len(os.read(fd_dvr, 131072))
                except OSError:
                    pass
        elapsed = time.monotonic() - t0
        return int(total * 8 / elapsed / 1000) if elapsed > 0 and total > 0 else 0
    except OSError:
        return 0
    finally:
        if fd_dvr >= 0:
            try:
                os.close(fd_dvr)
            except OSError:
                pass
        if fd_dmx >= 0:
            try:
                os.close(fd_dmx)
            except OSError:
                pass


class NOVBitrate(Converter, object):
    def __init__(self, type):
        Converter.__init__(self, type)
        self.novtype = type
        self.vcur = 0
        self._measuring = False
        self.pollTimer = eTimer()
        self.pollTimer.callback.append(self.poll)
        self.pollTimer.start(200, True)  # short initial delay

    def _get_channel_info(self):
        try:
            svc = self.source.service
            if not svc:
                return 0, 0, 0
            stream = svc.stream()
            if not stream:
                return 0, 0, 0
            sd = stream.getStreamingData()
            if not sd:
                return 0, 0, 0
            adapter = max(0, int(sd.get('adapter', 0) or 0))
            demux = max(0, int(sd.get('demux', 0) or 0))
            info = svc.info()
            if not info:
                return 0, 0, 0
            vpid = info.getInfo(iServiceInformation.sVideoPID)
            if vpid <= 0:
                return 0, 0, 0
            return adapter, demux, vpid
        except Exception:
            return 0, 0, 0

    def _do_measure(self, adapter, demux, vpid):
        try:
            kbps = _measure_bitrate(adapter, demux, vpid)
            self.vcur = kbps
        except Exception:
            pass
        finally:
            self._measuring = False

    def _kick(self):
        """Start a measurement immediately if not already running."""
        adapter, demux, vpid = self._get_channel_info()
        if vpid > 0 and not self._measuring:
            self._measuring = True
            threading.Thread(
                target=self._do_measure,
                args=(adapter, demux, vpid),
                daemon=True
            ).start()

    def poll(self):
        try:
            self._kick()
            Converter.changed(self, (self.CHANGED_POLL,))
        except Exception:
            pass
        self.pollTimer.start(2000, True)

    @cached
    def getText(self):
        if self.vcur > 0:
            return '%.1f Mb/s' % (self.vcur / 1000.0)
        return ''

    text = property(getText)

    def doSuspend(self, s):
        if s == 0:
            self._kick()
            self.pollTimer.start(1700, True)  # first refresh after 1.7s on resume
        else:
            self.pollTimer.stop()
