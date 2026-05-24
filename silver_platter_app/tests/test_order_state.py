from unittest import TestCase

from silver_platter.order_state import (
    BrokerReconciliationSnapshot,
    IdempotencyRegistry,
    initial_order_state,
    reconcile_broker_timeout,
    transition_order_state,
)


class OrderStateTests(TestCase):
    def test_valid_state_transition(self):
        state = initial_order_state("o1")
        state, event = transition_order_state(state, "previewed")

        self.assertEqual("previewed", state.state)
        self.assertEqual("draft", event.from_state)
        self.assertEqual("previewed", event.to_state)

    def test_invalid_state_transition_raises(self):
        state = initial_order_state("o1")

        with self.assertRaises(ValueError):
            transition_order_state(state, "filled")

    def test_idempotency_registry_blocks_duplicate(self):
        registry = IdempotencyRegistry()

        first = registry.reserve("key-1", "o1")
        second = registry.reserve("key-1", "o2")

        self.assertTrue(first.accepted)
        self.assertFalse(second.accepted)
        self.assertTrue(second.duplicate)
        self.assertEqual("o1", second.existing_order_id)

    def test_reconcile_broker_timeout_updates_filled_state(self):
        state = initial_order_state("o1")
        state, _ = transition_order_state(state, "previewed")
        state, _ = transition_order_state(state, "submitted")

        reconciled, event = reconcile_broker_timeout(
            state,
            BrokerReconciliationSnapshot(
                order_id="o1",
                broker_status="filled",
                filled_quantity=10,
                reason="broker poll after timeout",
            ),
        )

        self.assertEqual("filled", reconciled.state)
        self.assertEqual(10, reconciled.filled_quantity)
        self.assertEqual("submitted", event.from_state)
        self.assertEqual(10, event.filled_quantity_delta)
