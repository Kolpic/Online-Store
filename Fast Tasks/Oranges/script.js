document.addEventListener('DOMContentLoaded', () => {
    const input = [8, 10, 4]; // test cases: [100, 100, 60]; [100, 100,60]
    const firstOrange = [4, 8]; // test cases:  [1, 1];       [1, 1] 
    const secondOrange = [2, 7]; // test cases:  [100,100]     [50, 50]

    let row = input[0];
    let cols = input[1];
    let day = input[2];
    let firstOrangeRow = firstOrange[0];
    let firstOrangeCol = firstOrange[1];
    let secondOrangeRow = secondOrange[0];
    let secondOrangeCol = secondOrange[1];
    // proverka za double 
    if (row <= 0 || row > 10000) {
        alert('First number (rows) showld be between 1 and 10 000');
        return
    }
    if (cols <= 0 || cols > 10000) {
        alert('Second number (columns) showld be between 1 and 10 000');
        return
    }
    if (day <= 0 && day > 1000) {
        alert('Third number (days) showld be between 1 and 1000');
        return
    }
    if (firstOrangeRow > row || firstOrangeRow < 0 || firstOrangeCol > cols || firstOrangeCol < 0) {
        alert('First orange is out of bounds');
        return
    }
    if (secondOrangeRow > row || secondOrangeRow < 0 || secondOrangeCol > cols || secondOrangeCol < 0) {
        alert('Second orange is out of bounds');
        return
    }

    initialize(input, firstOrange, secondOrange); // Initialize the grid

    let currentDay = 0;
    const days = input[2];
    document.getElementById('next-day-btn').addEventListener('click', () => {
        if (currentDay < days) {
            currentDay++;
            updateGrid(currentDay);
            document.getElementById('day-counter').innerHTML = `Day: ${currentDay - 1}`;
        } else {
            alert('Simulation complete');
            console.log('Simulation complete');
        }
    });
});

function initialize(input, firstOrange, secondOrange) {
    let [rows, cols] = input.map(Number);
    let gridContainer = document.getElementById('grid-container');
    gridContainer.style.gridTemplateColumns = `repeat(${cols}, 10px)`;

    window.matrix = Array(rows).fill(0).map(() => Array(cols).fill(0));
    matrix[firstOrange[0] - 1][firstOrange[1] - 1] = 1;
    matrix[secondOrange[0] - 1][secondOrange[1] - 1] = 1;

    // Create initial grid
    for (let row = 0; row < rows; row++) {
        for (let col = 0; col < cols; col++) {
            let orange = document.createElement('div');
            orange.className = 'orange';
            if (matrix[row][col] > 0) {
                orange.classList.add('bad-orange');
            }
            gridContainer.appendChild(orange);
        }
    }
}

function updateGrid(day) {
    increaseTheDeadOranges(matrix, day);
    // Update DOM elements to reflect changes
    let rows = matrix.length;
    let cols = matrix[0].length;
    let gridContainer = document.getElementById('grid-container');
    
    for (let row = 0; row < rows; row++) {
        for (let col = 0; col < cols; col++) {
            if (matrix[row][col] === day) {
                gridContainer.children[row * cols + col].classList.add('bad-orange');
            }
        }
    }
}

function increaseTheDeadOranges(matrix, day) {
    let tempMatrix = matrix.map(row => [...row]); // Create a shallow copy of the matrix to avoid immediate updates

    for (let row = 0; row < matrix.length; row++) {
        for (let col = 0; col < matrix[row].length; col++) {
            if (matrix[row][col] === day) {
                if (row !== 0 && matrix[row - 1][col] === 0) {
                    tempMatrix[row - 1][col] = day + 1;
                }
                if (row !== matrix.length - 1 && matrix[row + 1][col] === 0) {
                    tempMatrix[row + 1][col] = day + 1;
                }
                if (col !== 0 && matrix[row][col - 1] === 0) {
                    tempMatrix[row][col - 1] = day + 1;
                }
                if (col !== matrix[row].length - 1 && matrix[row][col + 1] === 0) {
                    tempMatrix[row][col + 1] = day + 1;
                }
            }
        }
    }

    // Update the original matrix after all potential changes have been computed
    for (let row = 0; row < matrix.length; row++) {
        for (let col = 0; col < matrix[row].length; col++) {
            matrix[row][col] = tempMatrix[row][col];
        }
    }
}
