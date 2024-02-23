function solve(n, dataForMatrix) {
    let matrix = Array(n*n).fill(0).map(()=>Array(n*n).fill(0));
    let pointerMatrix = 0;
    let arrayWithUniqueElements = [];
    
    for (let i = 0; i < n * n; i++) {
        for (let j = 0; j < n * n; j++) {
            let matrixElement = String(dataForMatrix.split(" ")[pointerMatrix]);
            matrix[i][j] = matrixElement;
            if (arrayWithUniqueElements.filter(x => x==matrixElement)) {
                arrayWithUniqueElements.push(matrixElement);
            }
            pointerMatrix++;
        }
    }


    for (let i = 0; i < n * n; i++) {
        for (let j = 0; j < n * n; j++) {
            let metSumbols = [];
            let cuurentElement = matrix[i][j];
            if (cuurentElement == 0) {
                metSumbols = check(i, j, metSumbols, matrix, n);
            }
            let pointer = 0;
            let element = arrayWithUniqueElements.find(x => {
                if (x != metSumbols[pointer])
                pointer++;
            });
            matrix[i][j] = element;
        }
    }

    print(matrix);
}
function check(i, j, metSumbols, matrix, n) {
    let startingI = i;
    let startingJ = j;

    i = startingI;
    while(i != n * n + 1) {
        i++;
        let currentSymbol = String(matrix[i][j]);
        if (currentSymbol != 0 ) {
            metSumbols.push(currentSymbol);
        }
    }

    i = startingI;
    while(i != -1) {
        i--;
        let currentSymbol = matrix[i][j];
        if (currentSymbol != 0 ) {
            metSumbols.push(currentSymbol);
        }
    }

    i = startingI;
    while(j != -1) {
        j--;
        let currentSymbol = matrix[i][j];
        if (currentSymbol != 0 ) {
            metSumbols.push(currentSymbol);
        }
    }

    j = startingJ;
    while(j != n * n + 1) {
        j++;
        let currentSymbol = matrix[i][j];
        if (currentSymbol != 0 ) {
            metSumbols.push(currentSymbol);
        }
    }
    return metSumbols;
}

solve(2, "0 0 # $ 0 0 0 0 * 0 0 0 0 # 0 5");