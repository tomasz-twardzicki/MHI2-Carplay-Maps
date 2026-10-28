"""Small host-only import helper. SPDX-License-Identifier: GPL-3.0-or-later"""
import importlib.util


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
