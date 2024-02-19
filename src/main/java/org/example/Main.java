package org.example;

import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        String[] input = scanner.nextLine().split(" ");
        int rows = Integer.parseInt(input[0]);
        int cols = Integer.parseInt(input[1]);
        int days = Integer.parseInt(input[2]);

        int[][] matrix = new int[rows][cols];

        int counter = 0;
        while (counter != 2) {
            String[] coordinates = scanner.nextLine().split(" ");
            int row = Integer.parseInt(coordinates[0]) - 1;
            int col = Integer.parseInt(coordinates[1]) - 1;
            matrix[row][col] = 1;
            counter++;
        }

        for (int i = 1; i <= days; i++) {
            increaseTheDeadOranges(matrix, i);
        }

        int notDeadOranges = 0;
        for (int row = 0; row < matrix.length; row++) {
            for (int col = 0; col < matrix[row].length; col++) {
                if (matrix[row][col] == 0) {
                    notDeadOranges++;
                }
            }
        }
        System.out.println(notDeadOranges);
    }

    private static void increaseTheDeadOranges(int[][] matrix, int i) {
        for (int row = 0; row < matrix.length; row++) {
            for (int col = 0; col < matrix[row].length; col++) {
                int currentNumber = matrix[row][col];
                if (currentNumber == i) {
                    if (row != 0 && matrix[row - 1][col] == 0) {
                        matrix[row - 1][col] = i + 1;
                    }
                    if (row != matrix.length - 1 && matrix[row + 1][col] == 0) {
                        matrix[row + 1][col] = i + 1;
                    }
                    if (col != 0 && matrix[row][col - 1] == 0) {
                        matrix[row][col - 1] = i + 1;
                    }
                    if (col != matrix[row].length - 1 && matrix[row][col + 1] == 0) {
                        matrix[row][col + 1] = i + 1;
                    }
                }
            }
        }
    }
}