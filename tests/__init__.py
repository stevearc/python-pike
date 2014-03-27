""" Tests for pike """
import six
import unittest

from pike import Node


class ParrotNode(Node):

    """ Dummy node that just spits out a preset value """

    name = 'parrot'

    def __init__(self, value):
        super(ParrotNode, self).__init__()
        self.value = value

    def process(self, default=None, **kwargs):
        return self.value

# pylint: disable=E1101
if six.PY3:  # pragma: no cover
    unittest.TestCase.assertItemsEqual = unittest.TestCase.assertCountEqual
