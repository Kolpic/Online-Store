let array = [1, 2, 3, 4, 5, 6, 7];
 
array.push(77);
 
// console.log(array.toString());
// console.log(array.join(" ---> "));
// console.log(array.includes(77));
// console.log(array.includes("77"));
 
// for(let element of array) {
//     console.log(element);
// }
 
// JS Functions ///////////////////////////////////////////////
// Lady Bugs - ex 10
 
function ladyBugs(input) {
    let n = input.shift();// взимаме първи елемент от масива и го махаме от там, масивът се модифицира и става по-малък
    let field = (new Array(n)).fill(0);
    let ladyBugIndexes = input.shift().split(" ");
 
    for (let index of ladyBugIndexes) {
        index = Number(index);
        if (index >= 0 && index < n) {
            field[index] = 1;
        }
    }
 
    for (let command of input) {
        let tokens = command.split(" ");
        let startingIndex = Number(tokens[0]);
        if (field[startingIndex] == 1) {
            let currentIndex = startingIndex;
            let direction = tokens[1];
            let offset = Number(tokens[2]);
 
            if (direction == "left") {
                offset *= -1;
            }
 
            while (currentIndex >= 0 && currentIndex < n && field[currentIndex] == 1) {
                currentIndex += offset;
            }
            field[startingIndex] = 0;
            if (currentIndex >= 0 && currentIndex < n) {
                field[currentIndex] = 1;
            }
        }
    }
    // console.log(field.join(" "));
}
// ladyBugs([3, '0 1', '0 right 1', '2 right 1']);
 
// JS - Arrays Advanced //////////////////////////////////
 
function solve(arr) {
    let k = arr.shift();// mahame purviq element ot masiva 
 
    let firstK = arr.slice(0, k); // rejem masiva ot nachalo do k (masivut e nepremenen)
    let lastK = arr.slice(-k); // rejem kraq na masiva (masivut e nepromenen)
 
    console.log(firstK.join(" "));
    console.log(lastK.join(" "));
}
 
// solve([2, 7, 8, 9]);
 
function kSequence(n, k) {
    let array = [1];
 
    for (let i = 0; i < n - 1; i++) {
        let slicedArray = array.slice(-k);
        let sum = 0;
        for (let i = 0; i < slicedArray.length; i++) {
            sum += slicedArray[i];
        }
        array.push(sum);
    }
    console.log(array.join(" "));
}
 
// kSequence(6,3);
// kSequence(8, 2);
// kSequence(9, 5);
 
function process(arr) {
    console.log(
        arr
        .filter((x, i) => i % 2 == 1)
        .map(x => x * 2)
        .reverse()
        .join(" ")
    );
}
 
// process([10, 15, 20, 25]);
 
function solve1(nums) {
    return nums.sort((a,b) => a - b).slice(0,2).join(" ");
}
 
// console.log(solve1([30, 15, 50, 5]));
 
// JS Examp Prep //////////////////////////////////////////////////////////////
 
function findHours(input) {
    let arrayNumbers = input.map(Number);
    let allStudents = Number(input[3]);
 
    let hourCounter = 0;
    while(allStudents > 0) {
        for (let i = 0; i < 3; i++) {
            allStudents -= arrayNumbers[i];
        }
        hourCounter++;
        if (hourCounter % 4 == 0) {
            hourCounter++;
        }
    }
    console.log(`Time needed: ${hourCounter}h.`)
}
 
// findHours(["5", "6", "4","20"]);
// findHours(["1", "2", "3","45"]);
 
function arrayModifier(input) {
    let arrayNumbers = input.shift().split(" ").map(Number);
 
    let pointer = 0;
    while(input[pointer] != "end") {
        let func = input[pointer].split(" ")[0];
        let firstNumberIndex = Number(input[pointer].split(" ")[1]);
        let secondNmberIndex = Number(input[pointer].split(" ")[2]);
 
        if (func == "swap") {
            let temp = arrayNumbers[secondNmberIndex];
            arrayNumbers[secondNmberIndex] = arrayNumbers[firstNumberIndex];
            arrayNumbers[firstNumberIndex] = temp;
        } else if (func == "multiply") {
            arrayNumbers[firstNumberIndex] = arrayNumbers[firstNumberIndex] * arrayNumbers[secondNmberIndex];
        } else {
            for (let i = 0; i < arrayNumbers.length; i++) {
                arrayNumbers[i] -= 1;
            }
        }
        pointer++;
    }
    console.log(arrayNumbers.join(", "));
}
 
// arrayModifier(["23 -2 321 87 42 90 -123",
//                 "swap 1 3", 
//                 "swap 3 6",
//                 "swap 1 0",
//                 "multiply 1 2",
//                 "multiply 2 1",
//                 "decrease",
//                 "end"]);
 
function heartDelivery(input) {
    let houses = input.shift().split("@").map(Number);
 
    let cupidIndexPosition = 0;
    let line = 0;
    while(input[line] != "Love!") {
        let command = input[line].split(" ")[0];
        let indexesToJump = Number(input[line].split(" ")[1]);
 
        cupidIndexPosition += indexesToJump;
        if (cupidIndexPosition > houses.length - 1) {
            cupidIndexPosition = 0;
        }
 
        if (houses[cupidIndexPosition] <= 0) {
            console.log(`Place ${cupidIndexPosition} already had Valentine's day.`);
            continue;
        }
 
        houses[cupidIndexPosition] -= 2;
        if (houses[cupidIndexPosition] <= 0) {
            console.log(`Place ${cupidIndexPosition} has Valentine's day.`);
        }
        line++;
    }
 
    console.log(`Cupid's last position was ${cupidIndexPosition}.`);
    let isEveryHouseLoved = houses.every(houseValue => houseValue <= 0);
    if (isEveryHouseLoved) {
        console.log(`Mission was successful.`)
    } else {
        let housesCount = houses.filter(value => value > 0).length;
        console.log(`Cupid has failed ${housesCount} places.`);
    }
}
 
// heartDelivery(["10@10@10@2",
//               "Jump 1",
//               "Jump 2",
//               "Love!"]);
 
// JS - Objects and Classes
 
let person = {
    name: "Galin", 
    age: 21, 
    height: 173,
 
    sayHello: function() {
        console.log("Hi Bros");
    },
 
    sayHelloDiffertly() {
        console.log("Hi Brah")
    }
};
person["lastName"] = "Petrov";
person.isAlien = false;
person.sayAgainHello = function() {
    console.log("HII");
};
// console.log(person);
// person.sayHello();
// person.sayHelloDiffertly();
// person.sayAgainHello();
// console.log(Object.keys(person));
// console.log(Object.values(person));
// for(let key of Object.keys(person)) {
//     console.log(`${key}: ${person[key]}`);
// }
 
// JS - Associative Arrays /////////////////////////////
 
function phoneBook(input) {
    let book = {}
 
    for (let element of input) {
        let name = element.split(" ")[0];
        let number = Number(element.split(" ")[1]);
 
        book[name] = number;
    }
 
    for (let name in book) {
        console.log(`${name} -> ${book[name]}`);
    }
 
    console.log(book.hasOwnProperty("Tim"));
 
    delete book["Tim"];
 
    console.log(book.hasOwnProperty("Tim"));
 
    for (let name in book) {
        console.log(`${name} -> ${book[name]}`);
    }
}
 
 
// phoneBook(["Tim 0834212554", 
//           "Peter 08384112774",
//           "Bill 083826547", 
//           "Tim 08342129999"]);
 
function meetings(input) {
    let meeting = {}
 
    for (let command of input) {
        let token = command.split(" ");
        let day = token[0];
        let name = token[1];
 
        if (meeting.hasOwnProperty(day)) {
            console.log("Sloji drug den pacha, ne si zapisan!")
        } else {
            meeting[day] = name;
            console.log("Zpisa se!")
        }
    }
 
    for (let key in meeting) {
        console.log(key + " -> " + meeting[key]);
    }
}
 
// meetings(["Monday Peter", 
//           "Wednesday Bill",
//           "Monday Tim", 
//           "Friday Tim"]);
 
 
/* 
Object / Associative Arrays не могат да се сортират, затова
ако искаме да ги сортираме по някакъв 
критерии, от обект се превръщат в масив
и така може да се сортира, филтрира или мапне
*/
function sortAdderssBook(input) {
    let book = {};
 
    for (let token of input) {
        let name = token.split(":")[0];
        let place = token.split(":")[1];
 
        book[name] = place;
    }
 
    // Превръщане на обект в масив за да може да го сортираме
    let entries = Object.entries(book);
    console.log(entries); // Arrat of arrays
    console.log(entries[0]); // First array of arrays
    console.log(entries[0][0]); // First element of array in the arrays
    console.log(entries[0][1]); // Second element of array in the arrays
 
    let sorted = entries.sort((a,b) => {
        keyA = a[0];
        keyB = b[0];
        return keyA.localeCompare(keyB);// Сравняване на имената по азбучен ред (сортировка)
    });
 
    for (let [name, address] of sorted) {
        console.log(name + " -> " + address);
    }
}
 
// sortAdderssBook(["Tim:Doe Crossing", 
//           "Bill:Nelson Place",
//           "Peter:Carlyle Ave", 
//           "Bill:Ornery Rd"]);
 
let myMap = new Map();
myMap.set("one", 1);
myMap.set("two", 2);
myMap.set("three", 3);
myMap.set("four", 4);
 
let sortedMap = Array
                    .from(myMap.entries())
                    .sort((a,b) => a[1] - b[1]);
 
// for (let kvp of sortedMap) {
//     console.log(kvp[0] + " -> " + kvp[1]);
// }
 
// console.log(myMap);
 
function storage(input) {
    let map = new Map();
 
    for (let token of input) {
        let name = token.split(" ")[0];
        let number = Number(token.split(" ")[1]);
 
        if (map.has(name)) {
            let currentQuantity = map.get(name);
            map.set(name, currentQuantity + number);
        } else {
            map.set(name, number);
        }
    }
 
    for (let [key, value] of map) {
        console.log(key + "->" + value);
    }
}
 
// storage(["tomatoes 10",
//         "coffee 5",
//         "olives 100",
//         "coffee 40"]);
 
// JS - Text Processing //////////////////
 
// JS - Regular Expressions
 
let pattern = /[A-Z][a-z]+/g;
 
let text = "I am Rvery stuppppid Ramaned person Opasd 1960s";
 
let match1 = pattern.exec(text);
let match2 = text.match(pattern);
 
// console.log(match1);
// console.log(match2);
 
// JS Exam Preparation ////////////////////////////////////////////
 
function secretChat(input) {
    let wordToChange = input.shift();
 
    while(input[0] != "Reveal") {
        let tokens = input.shift().split(":|:");
        let command = tokens[0];
 
        if (command == "ChangeAll") {
            let subString = tokens[1];
            let subStringToReplaceWith = tokens[2];
 
            wordToChange = wordToChange.replaceAll(subString, subStringToReplaceWith);
        } else if (command == "Reverse") {
            let stringToReverse = tokens[1];
            if (wordToChange.includes(stringToReverse)) {
                wordToChange = wordToChange.replace(stringToReverse, "");
                let strToAdd = "";
                for (let i = stringToReverse.length -1 ; i >= 0; i--) {
                    strToAdd += stringToReverse.charAt(i);
                }
                wordToChange += strToAdd;
            } else {
                console.log("error")
            }
        } else if (command == "InsertSpace") {
            let index = Number(tokens[1]);
            let leftWord = wordToChange.slice(0, index);
            let rightWord = wordToChange.slice(index);
 
            let newWord = leftWord + " " + rightWord;
            wordToChange = newWord;
        }
        console.log(wordToChange);
    }
    console.log(`You have a new text message: ${wordToChange}`);
}
 
// secretChat(["heVVodar!gniV",
//     "ChangeAll:|:V:|:l",
//     "Reverse:|:!gnil",
//     "InsertSpace:|:5",
//     "Reveal"])
 
function mirrorWords(input) {
    let mirrorWordsPresent = {};
    let pattern = /(@|#)\w{3,}\1\1\w{3,}\1/gm;
 
    let match = input.match(pattern);
 
    if (match.length == 0) {
        console.log("No word pairs found!");
    } else {
        console.log(match.length + " word pairs found!")
    }
 
    for (let pair of match) {
        let symbol = pair.charAt(0);
        let word = pair.split(symbol + symbol);
        let leftWord = word[0].replace(symbol, "");
        let rightWord = word[1].replace(symbol, "");
 
        let changedWord = "";
        for (let i = rightWord.length - 1; i >= 0; i--) {
            changedWord += rightWord[i];
        }
 
        if (leftWord == changedWord) {
            mirrorWordsPresent[leftWord] = rightWord;
        }
    }
 
    if (Object.entries(mirrorWordsPresent).length != 0) {
        console.log("The mirror words are:")
        let mirrorWords = [];
        for (let [key, value] of Object.entries(mirrorWordsPresent)) {
            mirrorWords.push(`${key} <=> ${value}`);
        }
        console.log(mirrorWords.join(", "));
    } else {
        console.log("No mirror words!");
    }
}
 
// mirrorWords("@mix#tix3dj#poOl##loOp#wl@ @bong&song%4very$long@thong#Part##traP##@@leveL@@Level@##car#rac##tu@pack@@ckap@#rr#sAw##wAs#r#@w1r");
 
 
function heroesOfCodeAndLogic(input){
    let heroes = {};
    let commands = {
        CastSpell,
        TakeDamage,
        Recharge,
        Heal
    };
 
    let numberOfHeroes = Number(input.shift());
 
    while (numberOfHeroes != 0) {
        let hero = input.shift().split(" ");
        heroes[hero[0]] = [Number(hero[1]), Number([hero[2]])];
        numberOfHeroes--;
    }
 
    while (input != "End") {
        let tokens = input.shift().split(" - ");
        let command = tokens[0];
        let heroName = tokens[1];
        commands[command](tokens, heroName);
    }
 
    for (let values of Object.entries(heroes)) {
        console.log(`${values[0]}
                      HP: ${values[1][0]}
                      MP: ${values[1][1]}`);
    }
 
    function CastSpell(tokens, heroName) {
        let MPNeeded = Number(tokens[2]);
        let spellName = tokens[3];
 
        let remainingMP = heroes[heroName][1] - MPNeeded;
        if (remainingMP > 0) {
            heroes[heroName][1] = remainingMP;
            console.log(`${heroName} has successfully cast ${spellName} and now has ${remainingMP} MP!`);
        } else {
            console.log(`${heroName} does not have enough MP to cast ${spellName}!`);
        }
    }
 
    function TakeDamage(tokens, heroName) {
        let damage = Number(tokens[2]);
        let attaker = tokens[3];
 
        let remainingHP = heroes[heroName][0] - damage;
 
        if (remainingHP > 0) {
            heroes[heroName][0] = remainingHP;
            console.log(`${heroName} was hit for ${damage} HP by ${attaker} and now has ${remainingHP} HP left!`);
        } else {
            console.log(`${heroName} has been killed by ${attaker}!`);
            delete heroes[heroName];
        }
    }
 
    function Recharge(tokens, heroName) {
        let amount = Number(tokens[2]);
 
        currentMana = heroes[heroName][1];
        if (currentMana + amount > 200) {
            heroes[heroName][1] = 200;
        } else {
            heroes[heroName][1] = currentMana + amount;
        }
        console.log(`${heroName} recharged for ${amount} MP!`);
    }
 
    function Heal(tokens, heroName) {
        let amount = Number(tokens[2]);
 
        let currentHP = heroes[heroName][0];
        if (currentHP + amount > 100) {
            heroes[heroName][0] = 100;
        } else {
            heroes[heroName][0] = currentHP + amount;
        }
        console.log(`${heroName} healed for ${amount} HP!`);
    }
}
 
// heroesOfCodeAndLogic(["2",
//     "Solmyr 85 120",
//     "Kyrre 99 50",
//     "Heal - Solmyr - 10",
//     "Recharge - Solmyr - 50",
//     "TakeDamage - Kyrre - 66 - Orc",
//     "CastSpell - Kyrre - 15 - ViewEarth",
//     "End"]);
 
// JS- Exercises: Objects and Classes //////////////////////////////////////////////////
 
let cat = {
    name: "Kolpic",
    hello: (text) => console.log(text)
};
// console.log(cat);
cat.age = 5;
// console.log(cat);
cat["color"] = "Black";
// console.log(cat);
delete cat.color;
// console.log(cat);
// cat.hello("Mrrrr");
 
/*
console.log(Object.keys(cat)); // Array of obj keys 
console.log(Object.values(cat)); // Array of obj values
console.log(Object.entries(cat)); // Array of arrays - in pairs arr(key - value), arr(key-value)
 
console.log(Object.entries(cat)[0]); // Array with the key name amd value Kolpic
console.log(Object.entries(cat)[1]); // Array with the key hello amd value function
console.log(Object.entries(cat)[2]); // Array with the key age amd value 5
 
console.log(Object.entries(cat)[0][0]); // key name 
console.log(Object.entries(cat)[0][1]); // value Kolpic
*/
 
function employees(input) {
    class Empoyee {
        constructor(name, number) {
            this.name = name;
            this.number = number;
        }
 
    }
 
    let empNum = {};
    let listOfEmployees = [];
    let test = {};
 
    for (let i = 0; i < input.length; i++) {
        let name = input[i];
        let number = name.length;
        empNum[name] = number;
 
        let currentEmployee = new Empoyee(name, number);
        listOfEmployees.push(currentEmployee);
 
        test.name = name;
        test.number = number;
    }
 
    for (let [key, value] of Object.entries(empNum)) {
        console.log(`Name: ${key} -- Personal Number: ${value}`);
    }
 
    listOfEmployees.forEach(emp => console.log(`Name: ${emp.name} -- Personal Number: ${emp.number}`))
}
 
// employees([
//     'Silas Butler',
//     'Adnaan Buckley',
//     'Juan Peterson',
//     'Brendan Villarreal'
//     ]);
 
function towns(input) {
    let information = {};
    for (let command of input) {
        let tokens = command.split(" | ");
        let town = tokens[0];
        let latitude = tokens[1];
        let longitude = tokens[2];
 
        information.town = town;
        information.latitude = latitude;
        information.longitude = longitude;
 
        console.log(`town: ${information.town}, latitude: ${Number(information.latitude).toFixed(2)}, longitude: ${Number(information.longitude).toFixed(2)} }`)
    }
}
 
// towns(['Sofia | 42.696552 | 23.32601',
// 'Beijing | 39.913818 | 116.363625']
// );
 
function storeProvisions(input, input2) {
    let provisions = {};
    let length = input.length;
    for (let i = 0; i <= length - 1; i = i + 2) {
        provisions[input[i]] = Number(input[i + 1]);
    }
 
    for (let i = 0; i <= input2.length - 1; i = i + 2) {
        let product = input2[i];
        let quantity = Number(input2[i + 1]);
 
        if (provisions.hasOwnProperty(product)) {
            let currentQuantity = provisions[product];
            let finalQuantity = currentQuantity + quantity;
            delete provisions[product];
            console.log(product + " -> " + finalQuantity);
        } else {
            console.log(product + " -> " + quantity);
        }
    }
 
    for (let token of Object.entries(provisions)) {
        console.log(token[0] + " -> " + token[1]);
    }
}
 
// storeProvisions([
//     'Chips', '5', 'CocaCola', '9', 'Bananas', '14', 'Pasta', '4', 'Beer', '2'
//     ],
//     [
//     'Flour', '44', 'Oil', '12', 'Pasta', '7', 'Tomatoes', '70', 'Bananas', '30'
//     ]);
 
function movies(input) {
    let listOfMovies = [];
 
    for (let command of input) {
        if (command.includes("addMovie")) {
            let movie = command.split("addMovie ")[1];
            listOfMovies.push({name: movie})
        } else if (command.includes("directedBy")) {
            let tokens = command.split(" directedBy ")
            let movieName = tokens[0];
            let director = tokens[1];
            let movie = listOfMovies.find((movieObj) => movieObj.name === movieName);
            if (movie) {
                movie.director = director;
            }
        } else if (command.includes("onDate")) {
            let tokens = command.split(" onDate ")
            let movieName = tokens[0];
            let date = tokens[1];
            let movie = listOfMovies.find((movieObj) => movieObj.name === movieName);
            if (movie) {
                movie.date = date;
            }
        }
    }
    let onlyMoviesToPrint = listOfMovies.filter((movie) => movie.name != undefined 
    && movie.director != undefined && movie.date != undefined);
 
    console.log(JSON.stringify(onlyMoviesToPrint));
}
 
// movies([
//     'addMovie Fast and Furious',
//     'addMovie Godfather',
//     'Inception directedBy Christopher Nolan',
//     'Godfather directedBy Francis Ford Coppola',
//     'Godfather onDate 29.07.2018',
//     'Fast and Furious onDate 30.07.2018',
//     'Batman onDate 01.08.2018',
//     'Fast and Furious directedBy Rob Cohen'
//     ]);
// movies([
//     'addMovie The Avengers',
//     'addMovie Superman',
//     'The Avengers directedBy Anthony Russo',
//     'The Avengers onDate 30.07.2010',
//     'Captain America onDate 30.07.2010',
//     'Captain America directedBy Joe Russo'
//     ]);
 
function inventory(input) {
    let heroes = [];
 
    for (let command of input) {
        let tokens = command.split(" / ");
        let name = tokens[0];
        let level = Number(tokens[1]);
        let items = tokens[2].split(", ");
 
        heroes.push({
            name: name,
            level: level,
            items: items});
    }
 
    heroes.sort((a,b) => a.level > b.level ? 1 : -1);
 
    for (let heroValue of Object.values(heroes)) {
        console.log(`Hero: ${heroValue.name}` + "\n" + `level => ${heroValue.level}` + "\n" + `items => ${heroValue.items.toString()}`);
    }
}
 
// inventory([
//     'Isacc / 25 / Apple, GravityGun',
//     'Derek / 12 / BarrelVest, DestructionSword',
//     'Hes / 1 / Desolator, Sentinel, Antara'
//     ]);
 
function classStorage(input) {
    class Storage {
        constructor(capacity) {
            this.capacity = capacity;
            this.storage = [];
            this.totalCost = 0;
        }
 
        addProduct(product) {
            this.storage.push(product);
            let price = Number(product["price"]);
            let quantity = Number(product["quantity"]);
            this.capacity -= quantity;
            this.totalCost += (price * quantity);
        }
 
        getProducts() {
            return JSON.stringify(this.storage);
        }
    }
 
    let productOne = {name: 'Cucamber', price: 1.50, quantity: 15};
    let productTwo = {name: 'Tomato', price: 0.90, quantity: 25};
    let productThree = {name: 'Bread', price: 1.10, quantity: 8};
 
    let storage = new Storage(50);
 
    storage.addProduct(productOne);
    storage.addProduct(productTwo);
    storage.addProduct(productThree);
 
    console.log(storage.getProducts());
    console.log(storage.capacity);
    console.log(storage.totalCost);
}
 
// classStorage();
 
function catalogue(input) {
    let products = [];
 
    for (let token of input) {
        let productName = token.split(" : ")[0];
        let productPrice = Number(token.split(" : ")[1]);
        products.push({productName, productPrice});
    }
 
    products.sort((a,b) => a.productName.localeCompare(b.productName));
 
    let symbol = "@";
    for (let product of products) {
        let currentFirstLetter = product.productName.charAt(0);
        if (currentFirstLetter > symbol) {
            console.log(currentFirstLetter);
            symbol = currentFirstLetter;
        }
        console.log(`  ${product.productName}: ${product.productPrice}`)
    }
}
 
// catalogue([
//     'Appricot : 20.4',
//     'Fridge : 1500',
//     'TV : 1499',
//     'Deodorant : 10',
//     'Boiler : 300',
//     'Apple : 1.25',
//     'Anti-Bug Spray : 15',
//     'T-Shirt : 10'
//     ]
//     );
 
function vehicle(input) {
    class Vehicle {
        constructor(type, model, parts, fuel) {
            this.type = type;
            this.model = model;
            this.parts = parts;
            this.fuel = fuel;
        }
 
        drive(fuelLoss) {
            this.fuel -= fuelLoss;
        }
    }
    let parts = { engine: 6, power: 100 };
    parts.quality = parts.engine * parts.power;
 
    let vehicle = new Vehicle('a', 'b', parts, 200);
    vehicle.drive(100);
 
    console.log(vehicle.fuel);
    console.log(vehicle.parts.quality);
}
 
// vehicle();
 
function makeDictionary(input) {
    let dictionary = [];
 
    for (let command of input) {
        let parsedJson = JSON.parse(command);
        if (dictionary.hasOwnProperty(parsedJson.nam)) {
            let a;
        }
        dictionary.push(parsedJson);
    }
}
 
makeDictionary([
    '{"Coffee":"A hot drink made from the roasted and ground seeds (coffee beans) of a tropical shrub."}',
    '{"Bus":"A large motor vehicle carrying passengers by road, typically one serving the public on a fixed route and for a fare."}',
    '{"Boiler":"A fuel-burning apparatus or container for heating water."}',
    '{"Tape":"A narrow strip of material, typically used to hold or fasten something."}',
    '{"Microphone":"An instrument for converting sound waves into electrical energy variations which may then be amplified, transmitted, or recorded."}'
    ]);