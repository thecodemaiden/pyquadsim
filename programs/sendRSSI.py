from device_task import DeviceTask
import logging

class SendRssi(DeviceTask):
    """Just sit tight and record RSSI"""
    def setup(self):
        self.hasRadio = False # we need to make sure there is a radio before we can run the loop
        radio = self.device.getSensor('radio') # TODO: need gyro too for PID
        if radio is not None:
            self.hasRadio = True
            self.radio = radio
        self.lastTime = self.environment.time
        self.logger = logging.getLogger(name='Quadsim.{}'.format(self.device.name))
        return 0

    def loop(self):
        now = self.environment.time
        dt = now - self.lastTime
        # send a message to radio a1b2c3d4e5
        if self.hasRadio:
            # TODO: 'send' RSSI to RPi
            channel = self.radio.channel
            if self.radio.isAvailable():
                self.logger.info('[{}] RSSI: {}'.format(self.device.name, self.radio.lastRssi))

                p = self.radio.readPacket()
                # hardcoded RPi address
                self.radio.writePacket(now, 0xe7e7e7e7e1, channel, 0xf3) # todo, rssi value
        return 10

taskClass = SendRssi