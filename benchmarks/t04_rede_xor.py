"""Referencia Python do Teste 4 (rede neural XOR com backpropagation).

Mesma arquitetura e mesmos pesos iniciais do programa MiniPar
`programas_teste/t04_rede_neural_xor.mp`, usada apenas para comparar tempo.
"""

from __future__ import annotations

import math


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(0.0 - x))


def derivada_sigmoid(saida: float) -> float:
    return saida * (1.0 - saida)


class RedeNeuralXOR:
    def __init__(self) -> None:
        self.taxa_aprendizado = 0.5

        self.h1_w1 = 0.2
        self.h1_w2 = -0.4
        self.h1_bias = 0.0

        self.h2_w1 = -0.3
        self.h2_w2 = 0.6
        self.h2_bias = 0.1

        self.h3_w1 = 0.7
        self.h3_w2 = 0.5
        self.h3_bias = -0.2

        self.out_w1 = 0.4
        self.out_w2 = -0.5
        self.out_w3 = 0.3
        self.out_bias = 0.0

        self.h1 = 0.0
        self.h2 = 0.0
        self.h3 = 0.0
        self.saida = 0.0

    def feedforward(self, x1: float, x2: float) -> float:
        self.h1 = sigmoid((x1 * self.h1_w1) + (x2 * self.h1_w2) + self.h1_bias)
        self.h2 = sigmoid((x1 * self.h2_w1) + (x2 * self.h2_w2) + self.h2_bias)
        self.h3 = sigmoid((x1 * self.h3_w1) + (x2 * self.h3_w2) + self.h3_bias)

        self.saida = sigmoid(
            (self.h1 * self.out_w1)
            + (self.h2 * self.out_w2)
            + (self.h3 * self.out_w3)
            + self.out_bias
        )
        return self.saida

    def treinar_amostra(self, x1: float, x2: float, desejado: float) -> None:
        previsto = self.feedforward(x1, x2)
        erro = desejado - previsto
        delta_saida = erro * derivada_sigmoid(previsto)

        antigo_out_w1 = self.out_w1
        antigo_out_w2 = self.out_w2
        antigo_out_w3 = self.out_w3

        self.out_w1 += (self.h1 * delta_saida) * self.taxa_aprendizado
        self.out_w2 += (self.h2 * delta_saida) * self.taxa_aprendizado
        self.out_w3 += (self.h3 * delta_saida) * self.taxa_aprendizado
        self.out_bias += delta_saida * self.taxa_aprendizado

        delta_h1 = (delta_saida * antigo_out_w1) * derivada_sigmoid(self.h1)
        delta_h2 = (delta_saida * antigo_out_w2) * derivada_sigmoid(self.h2)
        delta_h3 = (delta_saida * antigo_out_w3) * derivada_sigmoid(self.h3)

        self.h1_w1 += (x1 * delta_h1) * self.taxa_aprendizado
        self.h1_w2 += (x2 * delta_h1) * self.taxa_aprendizado
        self.h1_bias += delta_h1 * self.taxa_aprendizado

        self.h2_w1 += (x1 * delta_h2) * self.taxa_aprendizado
        self.h2_w2 += (x2 * delta_h2) * self.taxa_aprendizado
        self.h2_bias += delta_h2 * self.taxa_aprendizado

        self.h3_w1 += (x1 * delta_h3) * self.taxa_aprendizado
        self.h3_w2 += (x2 * delta_h3) * self.taxa_aprendizado
        self.h3_bias += delta_h3 * self.taxa_aprendizado

    def treinar(self, epocas: int = 20000) -> None:
        for _ in range(epocas):
            self.treinar_amostra(0, 0, 0)
            self.treinar_amostra(0, 1, 1)
            self.treinar_amostra(1, 0, 1)
            self.treinar_amostra(1, 1, 0)

    def testar(self) -> None:
        print("==== Teste 4: rede neural XOR com backpropagation ====")
        print("Input: [0, 0], Predicted Output:", self.feedforward(0, 0))
        print("Input: [0, 1], Predicted Output:", self.feedforward(0, 1))
        print("Input: [1, 0], Predicted Output:", self.feedforward(1, 0))
        print("Input: [1, 1], Predicted Output:", self.feedforward(1, 1))


def main() -> None:
    rede = RedeNeuralXOR()
    rede.treinar()
    rede.testar()


if __name__ == "__main__":
    main()
