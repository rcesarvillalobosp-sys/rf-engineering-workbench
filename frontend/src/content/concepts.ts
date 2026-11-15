// Conceptos del modo educativo. Redacción técnica: distinguir siempre modelo matemático y medición.
export const CONCEPTS: { term: string; formula: string; text: string }[] = [
  {
    term: "Impedancia",
    formula: "Z = R + jX  [Ω]",
    text: "Relación compleja entre tensión y corriente senoidales en régimen permanente (Z = V/I). R representa disipación de potencia; X, almacenamiento de energía. Depende de la frecuencia salvo en una resistencia ideal.",
  },
  {
    term: "Reactancia",
    formula: "X_L = ωL ;  X_C = −1/(ωC)",
    text: "Parte imaginaria de Z. Con la convención e^{+jωt}, la reactancia inductiva es positiva (mitad superior de la carta de Smith) y la capacitiva negativa (mitad inferior). No disipa potencia media.",
  },
  {
    term: "Admitancia",
    formula: "Y = 1/Z = G + jB  [S]",
    text: "Inversa de la impedancia. Es más cómoda para elementos en paralelo, cuyas admitancias se suman. B > 0 es capacitiva y B < 0 inductiva. En la carta de Smith, y se obtiene girando z 180°.",
  },
  {
    term: "Coeficiente de reflexión",
    formula: "Γ = (Z − Z0)/(Z + Z0)",
    text: "Cociente complejo entre la onda de tensión reflejada y la incidente en un plano de referencia, respecto a una impedancia de referencia Z0. Para cargas pasivas |Γ| ≤ 1. Es la coordenada cartesiana de la carta de Smith.",
  },
  {
    term: "ROE / VSWR",
    formula: "VSWR = (1 + |Γ|)/(1 − |Γ|)",
    text: "Relación entre los máximos y mínimos de la envolvente de tensión de la onda estacionaria en una línea sin pérdidas. No contiene información de fase: dos cargas muy distintas pueden tener el mismo VSWR.",
  },
  {
    term: "Return Loss",
    formula: "RL = −20·log10|Γ|  [dB]",
    text: "Atenuación de la onda reflejada respecto a la incidente, expresada como número positivo. |S11| en dB es su opuesto. RL = 10 dB equivale a |Γ| = 0.316, VSWR ≈ 1.92 y un 10 % de potencia reflejada.",
  },
  {
    term: "Adaptación de impedancias",
    formula: "Zin = Zs*  (máxima transferencia)",
    text: "Red, normalmente sin pérdidas, que transforma la carga para que la fuente vea su conjugado. Con elementos reactivos la condición sólo es exacta a una frecuencia; el ancho de banda está acotado por el límite de Bode–Fano de la carga.",
  },
  {
    term: "Parámetros S",
    formula: "b = S·a",
    text: "Relacionan ondas de potencia incidentes (a) y reflejadas (b) en cada puerto, para una impedancia de referencia dada. S11 es reflexión en el puerto 1 con los demás terminados en Z0; S21 es transmisión del puerto 1 al 2. Cambiar Z0 cambia los valores.",
  },
  {
    term: "Líneas de transmisión",
    formula: "Zin = Z0·(ZL + Z0·tanh γℓ)/(Z0 + ZL·tanh γℓ)",
    text: "Cuando la longitud es comparable a λ, la tensión y la corriente varían a lo largo de la línea. La impedancia vista se transforma con la distancia: sobre la carta de Smith el punto gira alrededor del centro (círculo de |Γ| constante si no hay pérdidas), una vuelta cada λ/2.",
  },
];
