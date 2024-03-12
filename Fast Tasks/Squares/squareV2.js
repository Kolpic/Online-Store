let set = new Set();
let N;

function prepareMAtrix(n, grid, row, col)
{
	// валидация
    N = n * n
	
    let matrix = Array(n*n).fill(0).map(()=>Array(n*n).fill(0));
    let pointerMatrix = 0;
    
    for (let i = 0; i < n * n; i++) {
        for (let j = 0; j < n * n; j++) {
            let matrixElement = String(grid.split(" ")[pointerMatrix]);
            matrix[i][j] = matrixElement;
            set.add(matrixElement);
            pointerMatrix++;
        }
    }
    set.delete('0');
    solve(matrix, row, col)
}

function solve(matrix, row, col) {
	if (row == N - 1 && col == N) {
		return false;
    }

	if (col == N) {
		row++;
		col = 0;
	}

	if (matrix[row][col] != 0) {
		return solve(matrix, row, col + 1);
    }

	for(let num of set) {
		if (isSafe(matrix, row, col, num)) {
			matrix[row][col] = num;

			if (solve(matrix, row, col + 1)) {
				return true;
            }
		}

		matrix[row][col] = Number(0);
	}
	return false;
}

function isSafe(matrix, row, col, num) {
	for(let x = 0; x < N; x++) {
		if (matrix[row][x] == num) {
			return false;
        }
    }

	for(let x = 0; x < N; x++){
		if (matrix[x][col] == num) {
            return false;
        }
    }

	let startRow = row - row % Math.sqrt(N), 
		startCol = col - col % Math.sqrt(N);
		
	for(let i = 0; i < Math.sqrt(N); i++) {
		for(let j = 0; j < Math.sqrt(N); j++){
			if (matrix[i + startRow][j + startCol] == num) {
                return false; 
            }
        }				
    }
	return true;
}

let n = 2
let grid = "0 0 # $ 0 0 0 0 * 0 0 0 0 # 0 5"

if (prepareMAtrix(n, grid, 0, 0)) {
    let a = 5
	print(grid)
} else {
    document.write("no solution exists ")
}

