"""Watch-me-play recording engine (M5).

Captura simultânea de frame de tela + estado de input (teclado e mouse
via :mod:`pynput`) a 15-30 Hz, gravando PNGs em disco e linhas em
``recording_frames`` por thread separada. Endpoint chama
:meth:`Recorder.start`/``stop``/``status`` que sempre operam num
singleton mantido em :mod:`main`.
"""
