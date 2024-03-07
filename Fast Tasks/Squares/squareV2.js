function solveSudoku(n, grid, row, col)
{
	N = n * n
	
    let matrix = Array(n*n).fill(0).map(()=>Array(n*n).fill(0));
    let pointerMatrix = 0;
    let set = new Set();
    
    for (let i = 0; i < n * n; i++) {
        for (let j = 0; j < n * n; j++) {
            let matrixElement = String(grid.split(" ")[pointerMatrix]);
            matrix[i][j] = matrixElement;
            set.add(matrixElement);
            pointerMatrix++;
        }
    }

    set.delete('0');

	if (row == N - 1 && col == N)
		return true;

	if (col == N)
	{
		row++;
		col = 0;
	}

	if (grid[row][col] != 0)
		return solveSudoku(grid, row, col + 1);

	for(let num of set.values)
	{
		
		// Check if it is safe to place
		// the num (1-9) in the given 
		// row ,col ->we move to next column
		if (isSafe(grid, row, col, num))
		{
			
			/* assigning the num in the current
			(row,col) position of the grid and
			assuming our assigned num in the position
			is correct */
			grid[row][col] = num;

			// Checking for next
			// possibility with next column
			if (solveSudoku(grid, row, col + 1))
				return true;
		}
		
		/* removing the assigned num , since our
		assumption was wrong , and we go for next
		assumption with diff num value */
		grid[row][col] = 0;
	}
	return false;
}

/* A utility function to print grid */
function print(grid)
{
	for(let i = 0; i < N; i++)
	{
		for(let j = 0; j < N; j++)
			document.write(grid[i][j] + " ");
			
		document.write("<br>");
	}
}

// Check whether it will be legal
// to assign num to the
// given row, col
function isSafe(grid, row, col, num)
{
	
	// Check if we find the same num
	// in the similar row , we
	// return false
	for(let x = 0; x <= 8; x++)
		if (grid[row][x] == num)
			return false;

	// Check if we find the same num
	// in the similar column ,
	// we return false
	for(let x = 0; x <= 8; x++)
		if (grid[x][col] == num)
			return false;

	// Check if we find the same num
	// in the particular 3*3
	// matrix, we return false
	let startRow = row - row % 3, 
		startCol = col - col % 3;
		
	for(let i = 0; i < 3; i++)
		for(let j = 0; j < 3; j++)
			if (grid[i + startRow][j + startCol] == num)
				return false;

	return true;
}

let n = 2
let grid = ["0 0 # $ 0 0 0 0 * 0 0 0 0 # 0 5"]

if (solveSudoku(n, grid, 0, 0))
	print(grid)
else
	document.write("no solution exists ")

