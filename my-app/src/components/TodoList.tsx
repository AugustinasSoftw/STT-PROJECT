"use client";

import { useState } from "react";
import { Card } from "./ui/card";
import { Checkbox } from "./ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { ScrollArea } from "./ui/scroll-area";
import { Button } from "./ui/button";
import { CalendarIcon } from "lucide-react";

import { Calendar } from "./ui/calendar";
import { format } from "date-fns";

const TodoList = () => {
  const [date, setDate] = useState<Date | undefined>(new Date());
  const [open, setOpen] = useState(false);

  return (
    <div>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button className="w-full">
            <CalendarIcon />
            {date ? format(date, "PPP") : <span>Pick a date</span>}
          </Button>
        </PopoverTrigger>
        <PopoverContent>
          <Calendar
            mode="single"
            selected={date}
            onSelect={(date) => {
              setDate(date);
              setOpen(false);
            }}
            className="rounded-lg border"
          />
        </PopoverContent>
      </Popover>
      <ScrollArea className="max-h-[400px] mt-4 overflow-y-auto">
        <Card className="p-4">
          <div className="flex items-center gap-4">
            <Checkbox id="item1" />
            <label htmlFor="item1" className="text-muted-foreground">
              dasfdssssssss
            </label>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-4">
            <Checkbox id="item1" />
            <label htmlFor="item1" className="text-muted-foreground">
              dasfdssssssss
            </label>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-4">
            <Checkbox id="item1" />
            <label htmlFor="item1" className="text-muted-foreground">
              dasfdssssssss
            </label>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-4">
            <Checkbox id="item1" />
            <label htmlFor="item1" className="text-muted-foreground">
              dasfdssssssss
            </label>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-4">
            <Checkbox id="item1" />
            <label htmlFor="item1" className="text-muted-foreground">
              dasfdssssssss
            </label>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-4">
            <Checkbox id="item1" />
            <label htmlFor="item1" className="text-muted-foreground">
              dasfdssssssss
            </label>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-4">
            <Checkbox id="item1" />
            <label htmlFor="item1" className="text-muted-foreground">
              dasfdssssssss
            </label>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-4">
            <Checkbox id="item1" />
            <label htmlFor="item1" className="text-muted-foreground">
              dasfdssssssss
            </label>
          </div>
        </Card>
      </ScrollArea>
    </div>
  );
};

export default TodoList;
