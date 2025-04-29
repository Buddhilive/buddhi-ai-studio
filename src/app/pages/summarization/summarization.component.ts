import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';

@Component({
  selector: 'berkeliumlabs-summarization',
  imports: [RouterLink, ReactiveFormsModule],
  templateUrl: './summarization.component.html',
  styleUrl: './summarization.component.scss',
})
export class SummarizationComponent implements OnInit {
  toolForm!: FormGroup;
  isInitializing = true;
  inProgress = false;

  ngOnInit(): void {
    this.initTool();
  }

  private initTool(): void {
    this.toolForm = new FormGroup({
      content: new FormControl('', Validators.required),
      response: new FormControl(''),
    });
  }

  summarize() {
    if (typeof Worker !== 'undefined') {
      const worker = new Worker(
        new URL('../../core/summarizer.worker', import.meta.url)
      );

      worker.onmessage = ({ data }) => {
        // console.log('Response: ', data);
        this.toolForm.get('response')?.setValue(data[0].summary_text);
        this.inProgress = false;
      };

      const data = {
        content: this.toolForm.get('content')?.value,
      };
      this.inProgress = true;
      worker.postMessage(data);
    } else {
      //
    }
  }

  clearContent() {
    this.toolForm.reset();
  }
}
