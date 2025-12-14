import { useState, useEffect } from 'react';
import type { ModelInfo, SelectedModel, ModelParams } from '../types';
import { getModels } from '../api';

interface Props {
  selectedModels: SelectedModel[];
  onChange: (models: SelectedModel[]) => void;
}

const defaultParams: ModelParams = {
  temperature: 0.7,
  max_tokens: 2048,
};

export function ModelSelector({ selectedModels, onChange }: Props) {
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getModels()
      .then(setAvailableModels)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const isSelected = (model: ModelInfo) =>
    selectedModels.some(
      (s) => s.provider === model.provider && s.model_name === model.model_id
    );

  const toggleModel = (model: ModelInfo) => {
    if (isSelected(model)) {
      onChange(
        selectedModels.filter(
          (s) => !(s.provider === model.provider && s.model_name === model.model_id)
        )
      );
    } else {
      onChange([
        ...selectedModels,
        {
          provider: model.provider,
          model_name: model.model_id,
          params: { ...defaultParams },
        },
      ]);
    }
  };

  const groupedModels = availableModels.reduce(
    (acc, model) => {
      if (!acc[model.provider]) acc[model.provider] = [];
      acc[model.provider].push(model);
      return acc;
    },
    {} as Record<string, ModelInfo[]>
  );

  if (loading) return <div className="model-selector loading">Loading models...</div>;
  if (error) return <div className="model-selector error">Error: {error}</div>;

  return (
    <div className="model-selector">
      <h3>Select Models</h3>
      {Object.entries(groupedModels).map(([provider, models]) => (
        <div key={provider} className="provider-group">
          <h4>{provider.charAt(0).toUpperCase() + provider.slice(1)}</h4>
          <div className="models-list">
            {models.map((model) => (
              <label key={`${model.provider}-${model.model_id}`} className="model-item">
                <input
                  type="checkbox"
                  checked={isSelected(model)}
                  onChange={() => toggleModel(model)}
                />
                <span>{model.display_name}</span>
              </label>
            ))}
          </div>
        </div>
      ))}
      {selectedModels.length > 0 && (
        <div className="selected-count">
          {selectedModels.length} model{selectedModels.length !== 1 ? 's' : ''} selected
        </div>
      )}
    </div>
  );
}
