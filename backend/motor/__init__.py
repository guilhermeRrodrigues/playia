"""Inferência do motor model treinado em M6.

Consome o ONNX produzido pelo trainer e devolve uma ação atômica
(:class:`MotorAction`) por frame. O loop hierárquico (M7) chama
``predict`` a 30 Hz; latência típica em CPU é 5-20 ms.
"""
