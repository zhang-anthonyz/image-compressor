"""Export tests for the packaging self-check entry point.

The test suite needs ``psnr``/``reopen`` from conftest to be importable; pytest
handles that automatically for fixtures, but plain helpers are imported here
explicitly by the pipeline tests.
"""
