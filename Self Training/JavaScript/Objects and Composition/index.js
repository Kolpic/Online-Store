function solve(city, population, treasury) {
    // First way
    let record = {
        name: city,
        pop: population,
        treasury: treasury,
    }
 
    // Second way
    // let record = {};
    // record.name = city;
    // record.population = population;
    // record.treasury = treasury;
 
    // Third way 
    // let record = {
    //     name: city,
    //     population,
    //     treasury,
    // }
 
    // console.log(record);
 
    // Object Destructuring 
    let {name, pop} = record;
    // console.log(name);
    // console.log(pop);
}
 
solve('Tortuga', 7000, 15000);
 
// Way to clone a object (clone with different reference)
let obj = {name: "Galin", years: 21};
let {...clonedObj} = obj;
// console.log(clonedObj);
// console.log(obj == clonedObj); // compare by reference 
 
// Objects as a associate arrays 
let phones = {
    'Ivan Petrov': '08979506101',
    'Petrov Ivan': '08966554552',
}
// console.log(phones['Ivan Petrov']);
// Interation - for in
// for (let key in phones) {
//     console.log(key); // takeing the key pair
//     console.log(phones[key]); // takeing value pair
// }
 
// Interation with methods
let names = Object.keys(phones);
let phone = Object.values(phones);
// console.log(names);
// console.log(phone);
 
// Interation with method and for of
let entries = Object.entries(phones); // entries - kvp (array of arrays)
// for (const kvp of entries) {
//     console.log(kvp);
// }
 
let car = {
    model: 'BMW',
    year: 2010,
    facelift: true,
    honk: function() { // Method with function expression
        console.log(`${this.model} Beep beep!`);
    },
    honk2: () => { // Method with arrow funtion
        console.log('Beep beep!');
    },
    honk3() { // Object method notation
        console.log('Beep beep!');
    }
}
car.honk();
 
// Change execution context
let singleHonk = car.honk; // Copy funtion reference
 
singleHonk(); // undefined bec we dont have obj to use this.model 
 
let russianMachine = {
    model: 'Lada',
}
 
russianMachine.bibitka = car.honk; // using car.honk reference with obj russianMachine
 
russianMachine.bibitka();