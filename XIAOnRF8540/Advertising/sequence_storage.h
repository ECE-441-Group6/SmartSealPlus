#ifndef SEQUENCE_STORAGE_H
#define SEQUENCE_STORAGE_H

#include <stdint.h>

// Initialize previously provisioned persistent sequence storage.
// Returns false if storage is missing, invalid, or unavailable.
bool initializeSequenceStorage();

// Obtain a sequence number that belongs to a safely reserved block.
// Returns false if no sequence can be safely issued.
bool getNextPersistentSequence(uint32_t* sequence);

#endif
