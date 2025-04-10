import sys
import os
sys.path.append(os.getcwd())

# Logging
import logging

# Crypto stuff
import hiplib.crypto
from hiplib.crypto import factory

import hiplib.utils
from hiplib.utils import misc;

class Governor():
	def __init__(self):
		self.yi_dict  = dict()

	def get_yi_dict():
		return self.yi_dict