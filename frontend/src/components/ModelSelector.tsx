import { useState, useEffect } from 'react';
import type { ModelInfo, SelectedModel, ModelParams } from '../types';
import { getModels } from '../api';

interface Props {
  selectedModels: SelectedModel[];
  onChange: (models: SelectedModel[]) => void;
}

const providerLabels: Record<string, string> = {
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  google: 'Google',
  lmstudio: 'LM Studio (Local)',
};

const defaultParams: ModelParams = {
  temperature: 0.7,
  max_tokens: 2048,
};

const buildOptionKey = (model: ModelInfo) => `${model.provider}:${model.model_id}`;

export function ModelSelector({ selectedModels, onChange }: Props) {
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string>('');
  const [customLabel, setCustomLabel] = useState<string>('');

  useEffect(() => {
    getModels()
      .then((models) => {
        setAvailableModels(models);
        if (models.length && !selectedKey) {
          setSelectedKey(buildOptionKey(models[0]));
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const modelsByProvider = availableModels.reduce(
    (acc, model) => {
      if (!acc[model.provider]) acc[model.provider] = [];
      acc[model.provider].push(model);
      return acc;
    },
    {} as Record<string, ModelInfo[]>
  );

  const getModelFromKey = (key: string) =>
    availableModels.find((m) => buildOptionKey(m) === key);

  const nextLabelForModel = (model: ModelInfo) => {
    const count = selectedModels.filter(
      (m) => m.provider === model.provider && m.model_name === model.model_id
    ).length;
    if (count === 0) return model.display_name;
    return `${model.display_name} #${count + 1}`;
  };

  const addModel = () => {
    const model = getModelFromKey(selectedKey);
    if (!model) return;

    const label = customLabel.trim() || nextLabelForModel(model);
    const params = { ...defaultParams, instance_label: label };

    onChange([
      ...selectedModels,
      {
        provider: model.provider,
        model_name: model.model_id,
        params,
      },
    ]);
    setCustomLabel('');
  };

  const updateLabel = (index: number, label: string) => {
    const trimmed = label.trim() || selectedModels[index].model_name;
    const next = [...selectedModels];
    next[index] = {
      ...selectedModels[index],
      params: { ...selectedModels[index].params, instance_label: trimmed },
    };
    onChange(next);
  };

  const removeModel = (index: number) => {
    onChange(selectedModels.filter((_, i) => i !== index));
  };

  if (loading) return <div className="model-selector loading">Loading models...</div>;
  if (error) return <div className="model-selector error">Error: {error}</div>;

  return (
    <div className="model-selector">
      <div className="selector-header">
        <div>
          <h3>Select Models</h3>
          <p className="selector-hint">
            Add multiple instances of the same model for side-by-side answers. Each entry keeps its own context.
          </p>
        </div>
        {selectedModels.length > 0 && (
          <div className="selected-count">
            {selectedModels.length} model{selectedModels.length !== 1 ? 's' : ''} selected
          </div>
        )}
      </div>

      <div className="add-row">
        <div className="add-inputs">
          <select
            value={selectedKey}
            onChange={(e) => setSelectedKey(e.target.value)}
            className="model-select"
          >
            {Object.entries(modelsByProvider).map(([provider, models]) => (
              <optgroup
                key={provider}
                label={providerLabels[provider] || provider}
              >
                {models.map((model) => (
                  <option key={buildOptionKey(model)} value={buildOptionKey(model)}>
                    {model.display_name} · {providerLabels[model.provider] || model.provider}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          <input
            type="text"
            placeholder="Optional instance label"
            value={customLabel}
            onChange={(e) => setCustomLabel(e.target.value)}
            className="label-input"
          />
        </div>
        <button className="add-btn" onClick={addModel} disabled={!selectedKey}>
          + Add model
        </button>
      </div>

      {selectedModels.length > 0 && (
        <div className="selected-models">
          {selectedModels.map((model, index) => (
            <div
              key={`${model.provider}-${model.model_name}-${index}`}
              className="selected-model-card"
            >
              <div className="card-top">
                <div>
                  <p className="model-label">
                    {model.params.instance_label || `${model.model_name} #${index + 1}`}
                  </p>
                  <p className="model-meta">
                    {providerLabels[model.provider] || model.provider} · {model.model_name}
                  </p>
                </div>
                <button className="icon-btn" onClick={() => removeModel(index)} aria-label="Remove model">
                  ✕
                </button>
              </div>
              <label className="inline-label">
                Display label
                <input
                  type="text"
                  value={model.params.instance_label || ''}
                  onChange={(e) => updateLabel(index, e.target.value)}
                />
              </label>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
