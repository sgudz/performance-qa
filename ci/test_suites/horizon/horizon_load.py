import time
import urlparse

from inspect import getmembers
from pprint import pprint

from rally import consts
from rally import osclients
from rally.common import logging
from rally.common import utils as rutils
from rally.common.i18n import _
from rally import exceptions
from rally.plugins.openstack import scenario
from rally.task import atomic
from rally.task import utils
from rally.task import validation
from rally.task import context

from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

LOG = logging.getLogger(__name__)


class SeleniumManager:
    display = None
    driver = None

    @staticmethod
    def get_display():
        if SeleniumManager.display is None:
            SeleniumManager.display = Display(visible=0, size=(1920, 1080))
            SeleniumManager.display.start()
        return SeleniumManager.display

    @staticmethod
    def cleanup_display():
        if SeleniumManager.display is not None:
            SeleniumManager.display.stop()
            SeleniumManager.display = None

    @staticmethod
    def get_driver():
        SeleniumManager.get_display()
        if SeleniumManager.driver is None:
            SeleniumManager.driver = webdriver.Firefox()
        return SeleniumManager.driver

    @staticmethod
    def cleanup_driver():
        if SeleniumManager.driver is not None:
            SeleniumManager.driver.close()
            SeleniumManager.driver = None


@context.configure(name="usercred", order=1000)
class UserCredContext(context.Context):

    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,

        "properties": {
            "name": {
                "type": "string"
            },
            "password": {
                "type": "string"
            }
        },
        "additionalProperties": False
    }

    DEFAULT_CONFIG = {
        "name": "admin",
        "password": "admin"
    }

    @logging.log_task_wrapper(LOG.info, _("Enter context: `UserCredContext`"))
    def setup(self):
        self.users = []
        self.passwords = []
        for i in range(0, len(self.context["users"])):
            self.users.append(self.context["users"][i]["credential"].username)
            self.passwords.append(self.context["users"][i]["credential"].password)

        for i in range(0, len(self.context["users"])):
            self.context["users"][i]["credential"].username = self.config["name"]
            self.context["users"][i]["credential"].password = self.config["password"]

    @logging.log_task_wrapper(LOG.info, _("Exit context: `UserCredContext`"))
    def cleanup(self):
        for i in range(0, len(self.context["users"])):
            self.context["users"][i]["credential"].username = self.users[i]
            self.context["users"][i]["credential"].password = self.passwords[i]


@context.configure(name="hor_flavors", order=999)
class HorFlavorsContext(context.Context):

    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,

        "properties": {
            "nof_flavors": {
                "type": "integer",
                "minimum": 1
            }
        },
        "additionalProperties": False
    }

    DEFAULT_CONFIG = {
        "nof_flavors": 1
    }

    @logging.log_task_wrapper(LOG.info, _("Enter context: `hor_flavors`"))
    def setup(self):
        """Create list of flavors."""
        self.context["flavors"] = {}

        create_args = {
            "ram": 64,
            "vcpus": 1,
            "disk": 0,
            "swap": 0,
            "ephemeral": 0
        }

        clients = osclients.Clients(self.context["admin"]["credential"])
        for i in range(0, self.config["nof_flavors"]):
            create_args["name"] = self.generate_random_name()
            flavor = clients.nova().flavors.create(**create_args)
            self.context["flavors"][create_args["name"]] = flavor.to_dict()
            LOG.debug("Created flavor with id '%s'" % flavor.id)

    @logging.log_task_wrapper(LOG.info, _("Exit context: `hor_flavors`"))
    def cleanup(self):
        """Delete created flavors."""
        clients = osclients.Clients(self.context["admin"]["credential"])
        for flavor in self.context["flavors"].values():
            with logging.ExceptionLogger(
                    LOG, _("Can't delete flavor %s") % flavor["id"]):
                rutils.retry(3, clients.nova().flavors.delete, flavor["id"])
                LOG.debug("Flavor is deleted %s" % flavor["id"])

@context.configure(name="selenium", order=1001)
class SeleniumContext(context.Context):

    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,

        "properties": {
            "items_per_page": {
                "type": "integer",
                "minimum": 1
            },
            "horizon_base_url": {
                "type": "string"
            }
        },
        "additionalProperties": False
    }

    DEFAULT_CONFIG = {
        "items_per_page": 10
    }

    def __init__(self, context):
        super(SeleniumContext, self).__init__(context)

    def login_to_horizon(self, horizon_base_url, username, password):
        login_url = urlparse.urljoin(horizon_base_url, "auth/login")
        driver = SeleniumManager.get_driver()
        driver.get(login_url)

        try:
            input_password = driver.find_element_by_id("id_password")
            if input_password is not None:
                input_login = driver.find_element_by_id("id_username")

                input_login.send_keys(username)
                input_password.send_keys(password)
                driver.find_element_by_id("loginBtn").click()
        except NoSuchElementException:
            raise Exception("Failed to login to Horizon")

    def set_number_of_items_per_page(self, horizon_base_url, nof_items):
        driver = SeleniumManager.get_driver()

        settings_url = urlparse.urljoin(horizon_base_url, "settings")
        driver.get(settings_url)
        input_pagesize = driver.find_element_by_id("id_pagesize")
        input_pagesize.clear()
        input_pagesize.send_keys(str(nof_items))
        btn_save = driver.find_element_by_class_name("btn")
        btn_save.click()

    @logging.log_task_wrapper(LOG.info, _("Enter context: `PaginationContext`"))
    def setup(self):
        username = self.context["users"][0]["credential"].username
        password = self.context["users"][0]["credential"].password

        self.login_to_horizon(self.config["horizon_base_url"], username, password)
        self.set_number_of_items_per_page(self.config["horizon_base_url"], self.config["items_per_page"])

        self.context["horizon_base_url"] = self.config["horizon_base_url"]
    
    @logging.log_task_wrapper(LOG.info, _("Exit context: `PaginationContext`"))
    def cleanup(self):
        SeleniumManager.cleanup_driver()
        SeleniumManager.cleanup_display()

class HorizonLoadScenario(scenario.OpenStackScenario):

    @atomic.action_timer("horizon_performance.open_page")
    def _open_page(self, page):
        try:
            LOG.debug("Trying to open page '{}'".format(page))
            driver = SeleniumManager.get_driver()
            driver.get(page)
            count_span = WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.CLASS_NAME, "table_count")))
            return count_span
        except NoSuchElementException:
            raise Exception("NoSuchElementException, table count span is not found")
        except TimeoutException:
            raise Exception("TimeoutException, table count span is not found")

    @validation.required_openstack(users=True)
    @scenario.configure()
    def open_page(self, page, nof_items):
        page_to_open = urlparse.urljoin(self.context["horizon_base_url"], page)
        count_span = self._open_page(page_to_open)
        if nof_items != -1:
            if "Displaying {} item".format(nof_items) not in count_span.text:
                LOG.error("count_span.text is '{}'".format(count_span.text))
                raise Exception("Invalid number of items: expected nof {}, actual message {}".format(nof_items, count_span.text))
        else:
            LOG.debug("Nof items check disabled. Count span text is: '{}'".format(count_span.text))
