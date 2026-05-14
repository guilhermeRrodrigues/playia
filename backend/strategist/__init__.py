"""Loop hierárquico (M7): VLM estrategista (lento) + motor model ONNX (rápido).

Dois ``asyncio.Task`` cooperativos, encerrados por um ``asyncio.Event``:

- ``loop_strategist`` — captura tela e pede ao VLM uma INTENÇÃO em pt-br
  ("coletar madeira", "pular cacto", "evitar obstáculo à frente").
  Cadência depende da latência do VLM (5-15s no Mac com qwen2.5vl:3b).
- ``loop_motor`` — captura tela, roda o motor model ONNX e emite
  press/release de teclas conforme o diff vs frame anterior. Roda a
  30 Hz alvo (latência típica 5-20ms).

Na v0.1 o motor **não** usa a intenção como input — o frame contém
contexto suficiente para jogos simples (Chrome Dino). A intenção é
registrada no histórico e exibida na UI; quando o motor aprender a
condicionar em texto (M+), basta plugar aqui sem mexer no schema.
"""
