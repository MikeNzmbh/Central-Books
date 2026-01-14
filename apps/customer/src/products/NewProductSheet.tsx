import React, { useEffect, useState } from "react";
import {
    Button,
    Input,
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
    Textarea,
} from "../components/ui";

type ItemKind = "product" | "service";

interface NewProductSheetProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    defaultKind?: ItemKind;
    onCompleted: () => void;
}

export const NewProductSheet: React.FC<NewProductSheetProps> = ({
    open,
    onOpenChange,
    defaultKind = "product",
    onCompleted,
}) => {
    const [name, setName] = useState("");
    const [sku, setSku] = useState("");
    const [price, setPrice] = useState("");
    const [description, setDescription] = useState("");
    const [kind, setKind] = useState<ItemKind>(defaultKind);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!open) return;
        setError(null);
        setName("");
        setSku("");
        setPrice("");
        setDescription("");
        setKind(defaultKind);
    }, [open, defaultKind]);

    const canSubmit = name.trim().length > 0 && !saving;

    const onSubmit = async () => {
        if (!canSubmit) return;
        setSaving(true);
        setError(null);

        try {
            const response = await fetch("/api/products/create/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                credentials: "same-origin",
                body: JSON.stringify({
                    name: name.trim(),
                    sku: sku.trim() || undefined,
                    price: price ? parseFloat(price) : undefined,
                    description: description.trim() || undefined,
                    kind,
                }),
            });

            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data.error || data.detail || "Failed to create item");
            }

            onOpenChange(false);
            onCompleted();
        } catch (e: any) {
            setError(e?.message || "Failed to create item");
        } finally {
            setSaving(false);
        }
    };

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent>
                <SheetHeader>
                    <SheetTitle>New {kind === "service" ? "Service" : "Product"}</SheetTitle>
                    <SheetDescription>
                        Add a new {kind === "service" ? "service" : "product"} to your catalog.
                    </SheetDescription>
                </SheetHeader>

                <div className="mt-6 space-y-4">
                    <div>
                        <div className="text-xs font-medium text-slate-700 mb-1">Type</div>
                        <Select value={kind} onValueChange={(v) => setKind(v as ItemKind)}>
                            <SelectTrigger>
                                <SelectValue placeholder="Select type" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="product">Product</SelectItem>
                                <SelectItem value="service">Service</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    <div>
                        <div className="text-xs font-medium text-slate-700 mb-1">Name *</div>
                        <Input
                            placeholder="e.g. Premium Consulting"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                        />
                    </div>

                    <div>
                        <div className="text-xs font-medium text-slate-700 mb-1">SKU / Code</div>
                        <Input
                            placeholder="e.g. CONS-001"
                            value={sku}
                            onChange={(e) => setSku(e.target.value)}
                        />
                    </div>

                    <div>
                        <div className="text-xs font-medium text-slate-700 mb-1">Price</div>
                        <Input
                            inputMode="decimal"
                            placeholder="e.g. 99.00"
                            value={price}
                            onChange={(e) => setPrice(e.target.value)}
                        />
                    </div>

                    <div>
                        <div className="text-xs font-medium text-slate-700 mb-1">Description</div>
                        <Textarea
                            placeholder="Optional description..."
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            rows={3}
                        />
                    </div>

                    {error && (
                        <div className="text-sm text-rose-700 bg-rose-50 border border-rose-100 rounded-md p-2">
                            {error}
                        </div>
                    )}

                    <div className="flex items-center justify-end gap-2 pt-2">
                        <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
                            Cancel
                        </Button>
                        <Button onClick={onSubmit} disabled={!canSubmit}>
                            {saving ? "Creating…" : "Create"}
                        </Button>
                    </div>
                </div>
            </SheetContent>
        </Sheet>
    );
};

export default NewProductSheet;
