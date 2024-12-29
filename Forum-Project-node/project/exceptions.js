class WrongUserInputException extends Error {
	constructor(message, errorCode) {
		super(message);
		this.name = 'WrongUserInputException';
		this.errorCode = errorCode
	}
}

class DevException extends Error {
	constructor(message) {
		super(message);
		this.name = 'DevException'
	}
}

class PeerException extends Error {
	constructor(message, errorCode) {
		super(message);
		this.name = 'PeerException';
		this.errorCode = errorCode
	}
}

function AssertDev(condition, message) {
    if (!condition) {
        throw new DevException(message);
    }
}

function AssertUser(condition, message, errorCode) {
    if (!condition) {
        throw new WrongUserInputException(message, errorCode);
    }
}

function AssertPeer(condition, message, errorCode) {
    if (!condition) {
        throw new PeerException(message, errorCode);
    }
}

module.exports = {
	WrongUserInputException,
	DevException,
	PeerException,
	AssertDev,
    AssertUser,
    AssertPeer,
};