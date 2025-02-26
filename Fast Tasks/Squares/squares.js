function solve(n, dataForMatrix) {
    let matrix = Array(n*n).fill(0).map(()=>Array(n*n).fill(0));
    let pointerMatrix = 0;
    let set = new Set();
    
    for (let i = 0; i < n * n; i++) {
        for (let j = 0; j < n * n; j++) {
            let matrixElement = String(dataForMatrix.split(" ")[pointerMatrix]);
            matrix[i][j] = matrixElement;
            set.add(matrixElement);
            pointerMatrix++;
        }
    }

    set.delete('0');

    for (let i = 0; i < matrix.length; i++) {
        for (let j = 0; j <matrix[i].length; j++) {
            let metSumbols = [];
            let cuurentElement = matrix[i][j];
            if (cuurentElement == 0) {
                metSumbols = checkRowAndCol(i, j, metSumbols, matrix, n);
            } else {
                continue;
            }
            let tempSet = new Set(set);
            metSumbols.forEach(element => {
                if (tempSet.has(element)) {
                    tempSet.delete(String(element))
                }
            });
            let unique;
            if (tempSet.size > 1) {
                // metSumbols = check(i, j++, [], matrix, n)
                 unique = Array.from(tempSet)[1];
            } else {
                [unique] = tempSet;  
            }
            matrix[i][j] = unique;
        }
    }
    let a = 5;
}
function checkSubSquare(i, j, matrix, n) {

}

function checkRowAndCol(i, j, metSumbols, matrix, n) {
    let startingI = i;
    let startingJ = j;

    i = startingI;
    while(i != n * n - 1) {
        i++;
        let currentSymbol = String(matrix[i][j]);
        if (currentSymbol != 0 ) {
            metSumbols.push(currentSymbol);
        }
    }

    i = startingI;
    while(i != 0) {
        i--;
        let currentSymbol = matrix[i][j];
        if (currentSymbol != 0 ) {
            metSumbols.push(currentSymbol);
        }
    }

    i = startingI;
    while(j != 0) {
        j--;
        let currentSymbol = matrix[i][j];
        if (currentSymbol != 0 ) {
            metSumbols.push(currentSymbol);
        }
    }

    j = startingJ;
    while(j != n * n - 1) {
        j++;
        let currentSymbol = matrix[i][j];
        if (currentSymbol != 0 ) {
            metSumbols.push(currentSymbol);
        }
    }
    return metSumbols;
}

solve(2, "0 0 # $ 0 0 0 0 * 0 0 0 0 # 0 5");