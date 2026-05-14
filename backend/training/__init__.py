"""Behavioral cloning trainer (M6).

Treina uma policy network pequena (~350k params) supervisionada pelo
dataset de uma gravação watch-me-play, exporta como ONNX e registra em
``motor_models``. O motor model resultante é carregado pelo loop
hierárquico (M7) para gerar ações atômicas a 30 Hz.
"""
