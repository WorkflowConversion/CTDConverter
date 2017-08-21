#!/usr/bin/env python
# encoding: utf-8

"""
@author:     delagarza
"""

from CTDopts.CTDopts import ModelError


class CLIError(Exception):
    # Generic exception to raise and log different fatal errors.
    def __init__(self, msg):
        super(CLIError).__init__(type(self))
        self.msg = "E: %s" % msg

    def __str__(self):
        return self.msg

    def __unicode__(self):
        return self.msg


class InvalidModelException(ModelError):
    def __init__(self, message):
        super(InvalidModelException, self).__init__()
        self.message = message

    def __str__(self):
        return self.message

    def __repr__(self):
        return self.message


class ApplicationException(Exception):
    def __init__(self, msg):
        super(ApplicationException).__init__(type(self))
        self.msg = msg

    def __str__(self):
        return self.msg

    def __unicode__(self):
        return self.msg