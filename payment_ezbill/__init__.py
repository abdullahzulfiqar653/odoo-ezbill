from odoo.addons.payment import reset_payment_provider, setup_provider

from . import controllers
from . import models


def post_init_hook(env):
    setup_provider(env, 'ezbill')


def uninstall_hook(env):
    reset_payment_provider(env, 'ezbill')
