function solve(input, firstOrange, secondOrange) {
    let rows = Number(input[0]);
    let cols = Number(input[1]);
    let days = Number(input[2]);

    let matrix = Array(rows).fill(0).map(()=>Array(cols).fill(0));

    matrix[firstOrange[0] - 1][firstOrange[1] - 1] = 1;
    matrix[secondOrange[0] - 1][secondOrange[1] - 1] = 1;

    for(let i = 1; i <= days; i++) {
        increaseTheDeadOranges(matrix, i);
    }

    let notDeadOranges = 0;

    for (let row = 0; row < matrix.length; row++) {
        for (let col = 0; col < matrix[row].length; col++) {
            if (matrix[row][col] == 0) {
                notDeadOranges++;
            }
        }
    }
    console.log(notDeadOranges);

    function increaseTheDeadOranges(matrix, i) {
        for (let row = 0; row < matrix.length; row++) {
            for (let col = 0; col < matrix[row].length; col++) {
                let currentNumber = matrix[row][col];
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

solve([100, 100, 60], [1, 1], [50, 50]); 