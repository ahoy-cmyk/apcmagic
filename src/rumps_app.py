import rumps
import apcaccess
import logging

logger = logging.getLogger("apcmagic")

class APCApp(rumps.App):
    def __init__(self):
        super(APCApp, self).__init__("APC UPS Status")
        self.menu = ["Status", "Quit"]

    @rumps.clicked("Status")
    def status(self, _):
        try:
            status = apcaccess.get_status()
            rumps.alert(
                title="APC UPS Status",
                message=f"Status: {status['STATUS']}\n" \
                        f"Battery: {status['BCHARGE']}%\n" \
                        f"Load: {status['LOADPCT']}%\n" \
                        f"Time Left: {status['TIMELEFT']}",
            )
        except Exception as e:
            rumps.alert(title="Error", message=str(e))
            logger.error(f"Error in rumps app status: {e}")

