package shim

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestTaskStorage_Get(t *testing.T) {
	storage := NewTaskStorage()
	storedTask := Task{ID: "1", Status: TaskStatusRunning}
	storage.tasks["1"] = storedTask

	task, ok := storage.Get("1")
	assert.True(t, ok)
	assert.Equal(t, storedTask, task)

	task, ok = storage.Get("2")
	assert.False(t, ok)
	assert.NotEqual(t, storedTask, task)
}

func TestTaskStorage_Add_OK(t *testing.T) {
	storage := NewTaskStorage()
	storedTask := Task{ID: "1", Status: TaskStatusRunning}
	storage.tasks["1"] = storedTask
	addedTask := Task{ID: "2", Status: TaskStatusPending}

	ok := storage.Add(addedTask)
	assert.True(t, ok)
	assert.Equal(t, storedTask, storage.tasks["1"])
	assert.Equal(t, addedTask, storage.tasks["2"])
}

func TestTaskStorage_Add_AlreadyExists(t *testing.T) {
	storage := NewTaskStorage()
	storedTask := Task{ID: "1", Status: TaskStatusRunning}
	storage.tasks["1"] = storedTask

	ok := storage.Add(Task{ID: "1", Status: TaskStatusPending})
	assert.False(t, ok)
	assert.Equal(t, storedTask, storage.tasks["1"])
}

func TestTaskStorage_Update_OK(t *testing.T) {
	storage := NewTaskStorage()
	storedTask := Task{ID: "1", Status: TaskStatusRunning}
	storage.tasks["1"] = storedTask
	updatedTask := Task{ID: "1", Status: TaskStatusTerminated}

	ok := storage.Update(updatedTask)
	assert.True(t, ok)
	assert.Equal(t, updatedTask, storage.tasks["1"])
}

func TestTaskStorage_Update_DoesNotExist(t *testing.T) {
	storage := NewTaskStorage()

	ok := storage.Update(Task{ID: "1", Status: TaskStatusPending})
	assert.False(t, ok)
	assert.Equal(t, 0, len(storage.tasks))
}

func TestTaskStorage_Delete(t *testing.T) {
	storage := NewTaskStorage()
	storage.tasks["1"] = Task{ID: "1", Status: TaskStatusRunning}

	storage.Delete("2")
	assert.Equal(t, 1, len(storage.tasks))

	storage.Delete("1")
	assert.Equal(t, 0, len(storage.tasks))
}

func TestNewTask(t *testing.T) {
	cfg := TaskConfig{
		ID:   "66a886db-86db-4cf9-8c06-8984ad15dde2",
		Name: "vllm-0-0",
	}
	task := NewTask(cfg)

	assert.Equal(t, "66a886db-86db-4cf9-8c06-8984ad15dde2", task.ID)
	assert.Equal(t, "vllm-0-0-cff1b8da", task.containerName)
	assert.Equal(t, TaskStatusPending, task.Status)
	assert.Equal(t, cfg, task.config)
}

func TestGenerateUniqueName(t *testing.T) {
	testCases := []struct {
		name, id, expected string
	}{
		{"vllm-0-0", "66a886db-86db-4cf9-8c06-8984ad15dde2", "vllm-0-0-cff1b8da"},
		{"vllm-0-0", "41728e34-bf7e-41da-bf0e-0f46764b1752", "vllm-0-0-bb2a28c3"},
		{"llamacpp-0-0", "66a886db-86db-4cf9-8c06-8984ad15dde2", "llamacpp-0-0-58d1283d"},
	}
	for _, tc := range testCases {
		generated := generateUniqueName(tc.name, tc.id)
		assert.Equal(t, tc.expected, generated)
	}
}