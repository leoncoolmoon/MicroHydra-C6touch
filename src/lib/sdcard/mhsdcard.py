"""This simple module configures and mounts an SDCard."""

from .sdcard import _SDCard as _SDCard
import machine
import os



_MH_SDCARD_SLOT = const(1)
_MH_SDCARD_SCK = const(1)
_MH_SDCARD_MISO = const(3)
_MH_SDCARD_MOSI = const(2)
_MH_SDCARD_CS = const(4)



class SDCard:
    """SDCard control."""

    def __init__(self):
        """Initialize the SDCard."""
        try:
            self.sd = _SDCard(
                machine.SoftSPI(
                    baudrate=1320000,
                    sck=machine.Pin(_MH_SDCARD_SCK),
                    miso=machine.Pin(_MH_SDCARD_MISO),
                    mosi=machine.Pin(_MH_SDCARD_MOSI),
                ),
                cs=machine.Pin(_MH_SDCARD_CS),
            )
        except Exception as e:
            print(f"SDcard initialization failed: {e}")
            print("Continuing...")

                

    def mount(self):
        """Mount the SDCard."""
        if "sd" in os.listdir("/"):
            return
        try:
            os.mount(self.sd, '/sd')
        except (OSError, NameError, AttributeError) as e:
            print(f"Could not mount SDCard: {e}")


    def deinit(self):
        """Unmount and deinit the SDCard."""
        os.umount('/sd')
        # mh_if not shared_sdcard_spi:
        self.sd.deinit()
        # mh_end_if
