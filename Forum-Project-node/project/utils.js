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

module.exports = {
    AssertDev,
    AssertUser,
    AssertPeer,
}