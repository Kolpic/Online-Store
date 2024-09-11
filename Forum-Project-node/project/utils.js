const bcrypt = require('bcrypt');

const { DevException, WrongUserInputException, PeerException } = require('./exceptions');

function AssertDev(condition, message) {
    if (!condition) {
        throw new DevException(message);
    }
}

function AssertUser(condition, message) {
    if (!condition) {
        throw new WrongUserInputException(message);
    }
}

function AssertPeer(condition, message) {
    if (!condition) {
        throw new PeerException(message);
    }
}

async function hashPassword(password) {
    const saltRounds = 10;
    return await bcrypt.hash(password, saltRounds);
}

module.exports = {
    AssertDev,
    AssertUser,
    AssertPeer,
    hashPassword,
}