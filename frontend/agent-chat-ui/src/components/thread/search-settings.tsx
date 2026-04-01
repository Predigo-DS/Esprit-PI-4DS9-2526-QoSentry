import { Label } from "../ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { Slider } from "../ui/slider";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "../ui/tooltip";

type SearchSettingsProps = {
  searchType: "hybrid" | "semantic" | "keyword";
  onSearchTypeChange: (type: "hybrid" | "semantic" | "keyword") => void;
  rrfDenseWeight: number;
  onRrfDenseWeightChange: (weight: number) => void;
};

export function SearchSettings({
  searchType,
  onSearchTypeChange,
  rrfDenseWeight,
  onRrfDenseWeightChange,
}: SearchSettingsProps) {
  const showWeightSlider = searchType === "hybrid";

  return (
    <div className="flex flex-col gap-3 min-w-[280px]">
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex items-center gap-2">
              <Select
                value={searchType}
                onValueChange={(value) =>
                  onSearchTypeChange(value as "hybrid" | "semantic" | "keyword")
                }
              >
                <SelectTrigger className="w-[180px] h-8 text-sm">
                  <SelectValue placeholder="Search type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="hybrid">
                    <span className="flex items-center gap-2">
                      <span>🔍 Hybrid</span>
                      <span className="text-xs text-gray-500">(Semantic + Keyword)</span>
                    </span>
                  </SelectItem>
                  <SelectItem value="semantic">
                    <span className="flex items-center gap-2">
                      <span>💭 Semantic</span>
                      <span className="text-xs text-gray-500">(Meaning-focused)</span>
                    </span>
                  </SelectItem>
                  <SelectItem value="keyword">
                    <span className="flex items-center gap-2">
                      <span>🔤 Keyword</span>
                      <span className="text-xs text-gray-500">(Exact match)</span>
                    </span>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </TooltipTrigger>
          <TooltipContent>
            <p className="max-w-[250px] text-xs">
              {searchType === "hybrid" &&
                "Combines semantic understanding with keyword matching for best results"}
              {searchType === "semantic" &&
                "Searches by meaning and concepts, ignores exact keywords"}
              {searchType === "keyword" &&
                "Searches for exact keyword matches, ignores semantic meaning"}
            </p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      {showWeightSlider && (
        <div className="flex items-center gap-3 px-1">
          <Label
            htmlFor="rrf-weight"
            className="text-xs text-gray-600 min-w-[60px]"
          >
            Keyword
          </Label>
          <Slider
            id="rrf-weight"
            defaultValue={[1 - rrfDenseWeight]}
            onValueChange={(values) => onRrfDenseWeightChange(1 - values[0])}
            min={0}
            max={1}
            step={0.1}
            className="flex-1"
          />
          <Label
            htmlFor="rrf-weight"
            className="text-xs text-gray-600 min-w-[60px]"
          >
            Semantic
          </Label>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="text-xs text-gray-500 min-w-[45px] text-right">
                  {(rrfDenseWeight * 100).toFixed(0)}%
                </div>
              </TooltipTrigger>
              <TooltipContent side="top">
                <p className="text-xs">
                  Current: {(rrfDenseWeight * 100).toFixed(0)}% semantic,{" "}
                  {((1 - rrfDenseWeight) * 100).toFixed(0)}% keyword
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      )}
    </div>
  );
}
