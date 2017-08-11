#!/usr/bin/env python
# encoding: utf-8
import sys

MESSAGE_INDENTATION_INCREMENT = 2


def _get_indented_text(text, indentation_level):
    return ("%(indentation)s%(text)s" %
            {"indentation": "  " * (MESSAGE_INDENTATION_INCREMENT * indentation_level),
             "text": text})


def warning(warning_text, indentation_level=0):
    sys.stdout.write(_get_indented_text("WARNING: %s\n" % warning_text, indentation_level))


def error(error_text, indentation_level=0):
    sys.stderr.write(_get_indented_text("ERROR: %s\n" % error_text, indentation_level))


def info(info_text, indentation_level=0):
    sys.stdout.write(_get_indented_text("INFO: %s\n" % info_text, indentation_level))
