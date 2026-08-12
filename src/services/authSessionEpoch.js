export function createAuthSessionEpochController() {
  let generation = 0;
  let refreshOperation = null;

  return Object.freeze({
    current() {
      return generation;
    },

    advance() {
      generation += 1;
      refreshOperation = null;
      return generation;
    },

    isCurrent(candidateGeneration) {
      return candidateGeneration === generation;
    },

    getRefreshPromise(candidateGeneration, refreshToken) {
      if (
        refreshOperation?.generation !== candidateGeneration
        || refreshOperation?.refreshToken !== refreshToken
      ) {
        return null;
      }
      return refreshOperation.promise;
    },

    setRefreshPromise(candidateGeneration, refreshToken, promise) {
      if (candidateGeneration !== generation) return false;
      refreshOperation = {
        generation: candidateGeneration,
        refreshToken,
        promise,
      };
      return true;
    },

    clearRefreshPromise(promise) {
      if (refreshOperation?.promise === promise) refreshOperation = null;
    },
  });
}

export const authSessionEpoch = createAuthSessionEpochController();
