import kivy

import kivy.app
from kivy.clock import Clock
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.modalview import ModalView

from kivy.properties import StringProperty, NumericProperty

from kegbot.kegboard import kegboard, message
from kegbot.pycore.kegnet import KegnetClient
import kegbot.pycore.kbevent
import kegbot.util

from kegbot.api import kbapi
from kegbot.api.exceptions import NotFoundError

import time
import datetime
from pint import UnitRegistry

import threading
import ConfigParser as configparser
import pprint

class KegnetListener(threading.Thread, KegnetClient):
    running = True

    def __init__(self, *args, **kwargs):
        super(KegnetListener, self).__init__(*args, **kwargs)
        KegnetClient.__init__(self)
        self.start()

    def run(self):
        self.Listen()

    def onNewEvent(self, event):
        print(event)
        if isinstance(event, kegbot.pycore.kbevent.ThermoEvent):
            self.onThermoUpdate(event)
        elif isinstance(event, kegbot.pycore.kbevent.TokenAuthEvent):
            self.onTokenAuthEvent(event)
        elif isinstance(event, kegbot.pycore.kbevent.SetRelayOutputEvent):
            self.onSetRelayOutputEvent(event)

    def onThermoUpdate(self, event):
        pass

    def onDrinkCreated(self, event):
        print(event)

    def onFlowUpdate(self, event):
        print(event)

    def onSetRelayOutput(self, event):
        print(event)

    def onFlowRequest(self, event):
        print(event)

    def onTokenAuthEvent(self, event):
        print(event)

    def onSetRelayOutputEvent(self, event):
        print(event)


class RelayMessenger(threading.Thread):
    OPEN = 0
    CLOSED = 1

    status = [OPEN for _ in range(4)]

    interval = 1.0
    running = True

    def __init__(self, board, *args, **kwargs):
        super(RelayMessenger, self).__init__(*args, **kwargs)
        self.board = board

    def set_relay(self, relay, mode):
        self.status[relay] = mode
        self._update_relays()

    def _update_relays(self):
        for i in range(4):
            cmd = kegboard.SetOutputCommand()
            cmd.SetValue('output_id', i)
            cmd.SetValue('output_mode', self.status[i])
            self.board.write_message(cmd)

    def run(self):
        while self.running:
            self._update_relays()
            time.sleep(self.interval)

class AuthModal(ModalView):
    user = StringProperty()

    def __init__(self, *args, **kwargs):
        super(AuthModal, self).__init__(*args, **kwargs)

class TapScreen(Screen):
    keg_image_src = StringProperty()
    bev_name = StringProperty()
    bev_image_src = StringProperty(allownone=True)

    def __init__(self, *args, **kwargs):
        super(TapScreen, self).__init__(*args, **kwargs)

    def update(self, tap_properties):
        #print("Updating tap with info:\n{}".format(pprint.pformat(tap_properties)))
        keg = tap_properties.get('current_keg')
        beverage = keg.get('beverage')

        self.keg_image_src = keg['illustration_url']
        self.bev_name = beverage['name']

        bev_picture = beverage.get('picture')
        if (bev_picture is not None):
            self.bev_image_src = bev_picture.get('original_url')
        else:
            self.bev_image_src = ''

    def onAuthenticated(self, user):
        print("Tapscreen: authenticated")


class KegbotClient(kivy.app.App):
    temp_c = NumericProperty(0)
    temp_f = NumericProperty(0)

    config_path = '/etc/kegbot.conf'

    kegnet_client = None
    kbapi_client = None

    sm = None
    tap_properties = {}

    def __init__(self, *args, **kwargs):
        super(KegbotClient, self).__init__(*args, **kwargs)

        config = configparser.ConfigParser()
        config.read(self.config_path)

        self.kegnet_client = KegnetListener()
        self.kegnet_client.onThermoUpdate = self.onTempEvent
        self.kegnet_client.onTokenAuthEvent = self.onTokenEvent

        self.kbapi_client = kbapi.Client(
                config.get('kegbot', 'API_URL'), config.get('kegbot', 'API_KEY'))

        self.board = kegboard.wait_for_kegboard()
        self.board.open()

        self.relay_messenger = RelayMessenger(self.board)
        self.relay_messenger.start()

        self.register_event_type('on_valid_token')
        self.register_event_type('on_invalid_token')

        self.sm = ScreenManager()

        Clock.schedule_interval(self.update, 0.01)

    def build(self):
        return self.sm

    def update(self, *args):
        self._update_taps(self.kbapi_client.taps())

    def _update_taps(self, taps):
        for tap in taps:
            tap_name = tap['name']
            self.tap_properties[tap_name] = tap

            if not self.sm.has_screen(tap_name):
                self.sm.add_widget(TapScreen(name=tap_name))

        for tap_name in self.sm.screen_names:
            if tap_name not in self.tap_properties:
                tap_screens.remove(tap_name)

        for tap_name in self.sm.screen_names:
            self.sm.get_screen(tap_name).update(self.tap_properties[tap_name])

    def _change_relay_state(self, relay, mode):
        self.relay_messenger.set_relay(relay, mode)

    def onTokenEvent(self, event):
        for i in range(4):
            self._change_relay_state(i, 0)

        try:
            token = self.kbapi_client.get_token(event.auth_device_name, event.token_value)
        except NotFoundError:
            self.on_invalid_token()
            return

        self.on_valid_token()

    def on_invalid_token(self):
        for relay in range(0, 4):
            self._change_relay_state(relay, 0)

        return True

    def on_valid_token(self):
        for relay in range(0, 4):
            self._change_relay_state(relay, 1)

        return True

    def onTempEvent(self, event):
        self.onTempChange(event.sensor_value)

    def onTempChange(self, new_temp):
            self.temp_c = new_temp
            ureg = UnitRegistry()
            Q_ = ureg.Quantity
            self.temp_f, unit = Q_(
                    self.temp_c, ureg.degC).to('degF').to_tuple()

class TitleBar(Widget):
    def __init__(self, *args, **kwargs):
        super(TitleBar, self).__init__(*args, **kwargs)

class KegTemp(Label):
    display_temp = StringProperty('')

    def __init__(self, *args, **kwargs):
        super(KegTemp, self).__init__(*args, **kwargs)
        Clock.schedule_interval(self.update, 1)
        self.app = kivy.app.App.get_running_app()

    def update(self, *args):
        self.display_temp = '{:.2f} F'.format(self.app.temp_f)

class TitleClock(Label):
    display_time = StringProperty('')

    def __init__(self, *args, **kwargs):
        super(TitleClock, self).__init__(*args, **kwargs)
        Clock.schedule_interval(self.update, 1)

    def update(self, *args):
        self.display_time = datetime.datetime.now().strftime('%I:%M %p')

if __name__ == '__main__':
    KegbotClient.run()
